#!/usr/bin/env python3
"""
EnglishPartner 统一查询入口
============================
生产级设计：
  - 守护进程模式（Unix socket）避免重复加载索引
  - 客户端自动发现/启动守护进程
  - 优雅降级：daemon 不可用 → 直读索引（cold start）
  - 超时控制 + 并发安全 + 文件安全读取

用法:
  python3 query_engine.py word <word>
  python3 query_engine.py root <word>
  python3 query_engine.py pronounce <word>
  python3 query_engine.py daemon         # 启动长期守护进程
  python3 query_engine.py stop           # 停止守护进程
  python3 query_engine.py status         # 查看守护进程状态
"""
import json
import os
import socket
import struct
import sys
import time

# ──────────── 路径常量 ────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

DAEMON_SOCKET = "/tmp/english-partner.sock"
DAEMON_PID_FILE = "/tmp/english-partner.pid"
DAEMON_LOG = "/tmp/english-partner.log"


# ═══════════════════════════════════════════════
#  1. 直读查询（cold path，用于降级/首次启动）
# ═══════════════════════════════════════════════

def _direct_query(lib: str, word: str) -> dict:
    """直接调用 query_utils 查询（无 daemon 时的降级路径）"""
    from query_utils import get_word_data, get_root_data, get_pronounce_data

    GETTERS = {
        "word": get_word_data,
        "root": get_root_data,
        "pronounce": get_pronounce_data,
    }
    getter = GETTERS.get(lib)
    if not getter:
        return {}
    result = getter(word)
    return result if result else {}


# ═══════════════════════════════════════════════
#  2. 守护进程（长期驻留，单次加载所有索引）
# ═══════════════════════════════════════════════

def _daemon_serve():
    """
    守护进程主循环（线程安全，支持并发）：
      - 加载全部索引
      - Unix socket 监听，4 线程并发处理
      - 线程安全（GETTERS 字典多线程只读访问）
    """
    import signal as _signal
    from concurrent.futures import ThreadPoolExecutor

    MAX_WORKERS = 4  # 最多同时处理 4 个查询

    def log(msg):
        t = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(DAEMON_LOG, "a") as f:
            f.write(f"[{t}] {msg}\n")

    log("Daemon starting...")
    _shutdown_flag = False

    # 加载索引
    try:
        from query_utils import get_word_data, get_root_data, get_pronounce_data

        log("Loading word index...")
        get_word_data("__warmup__")
        log("Loading root index...")
        get_root_data("__warmup__")
        log("Loading pronounce index...")
        get_pronounce_data("__warmup__")
        log("All indexes loaded.")
    except Exception as e:
        log(f"Index load failed: {e}")
        sys.exit(1)

    # 写 PID 文件
    with open(DAEMON_PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # 清理旧 socket
    try:
        os.unlink(DAEMON_SOCKET)
    except OSError:
        pass

    # 创建 socket 监听（backlog=128，支持并发排队）
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(DAEMON_SOCKET)
    server.listen(128)
    os.chmod(DAEMON_SOCKET, 0o777)
    server.settimeout(1.0)

    log(f"Daemon ready on {DAEMON_SOCKET} (workers={MAX_WORKERS})")

    # 查询函数映射（只读，多线程安全）
    GETTERS = {
        "word": get_word_data,
        "root": get_root_data,
        "pronounce": get_pronounce_data,
    }

    def handle_query(conn):
        """线程内：处理单个客户端请求"""
        conn.settimeout(10.0)
        try:
            raw = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                raw += chunk
                if len(raw) > 100000:
                    raise ValueError("Request too large")
                if b"\n" in raw:
                    break

            data = raw.decode("utf-8").strip()
            if not data:
                raise ValueError("Empty request")

            req = json.loads(data)
            lib = req.get("lib", "")
            word = req.get("word", "").lower().strip()

            if lib not in GETTERS:
                raise ValueError(f"Unknown lib: {lib}")
            if not word or len(word) > 20:
                raise ValueError(f"Invalid word: {word}")

            result = GETTERS[lib](word) or {}
            resp = json.dumps(result, ensure_ascii=False) + "\n"
            conn.sendall(resp.encode("utf-8"))

        except json.JSONDecodeError as e:
            _safe_send(conn, {"error": f"JSON parse error: {e}"})
        except ValueError as e:
            _safe_send(conn, {"error": str(e)})
        except Exception as e:
            _safe_send(conn, {"error": f"Internal error: {e}"})
            log(f"Handler error: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _safe_send(conn, obj):
        try:
            conn.sendall(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
        except Exception:
            pass

    # 注册信号处理
    def _on_signal(signum, frame):
        nonlocal _shutdown_flag
        _shutdown_flag = True
        log(f"Signal {signum} received, shutting down...")

    _signal.signal(_signal.SIGTERM, _on_signal)
    _signal.signal(_signal.SIGINT, _on_signal)

    # 线程池
    pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    try:
        while not _shutdown_flag:
            try:
                conn, addr = server.accept()
                pool.submit(handle_query, conn)
            except socket.timeout:
                continue
            except Exception as e:
                if _shutdown_flag:
                    break
                log(f"Accept error: {e}")
                continue
    finally:
        log("Shutting down thread pool...")
        pool.shutdown(wait=False)
        server.close()
        try:
            os.unlink(DAEMON_SOCKET)
        except OSError:
            pass
        try:
            os.unlink(DAEMON_PID_FILE)
        except OSError:
            pass
        log("Daemon stopped")


# ═══════════════════════════════════════════════
#  3. 客户端（连接 daemon，有降级策略）
# ═══════════════════════════════════════════════

def _ensure_daemon() -> bool:
    """确保 daemon 在运行，返回 True=可用 / False=降级"""
    # 如果 pid 文件存在且进程还活着
    if os.path.exists(DAEMON_PID_FILE):
        try:
            with open(DAEMON_PID_FILE) as f:
                pid = int(f.read().strip())
            # 检查进程是否存在
            os.kill(pid, 0)
            return True  # 进程存活
        except (OSError, ValueError):
            # PID 文件过期
            pass

    # 尝试连接 socket
    if os.path.exists(DAEMON_SOCKET):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(DAEMON_SOCKET)
            s.close()
            return True  # socket 可用（虽然 pid 有问题）
        except Exception:
            pass

    # 尝试启动 daemon
    try:
        daemon_args = [sys.executable, os.path.abspath(__file__), "daemon"]
        pid = os.fork()
        if pid == 0:
            # 子进程：成为 daemon
            os.setsid()
            # 关闭标准 fd
            devnull = os.open(os.devnull, os.O_RDWR)
            os.dup2(devnull, 0)
            os.dup2(devnull, 1)
            os.dup2(devnull, 2)
            os.closerange(3, 256)
            # 执行 daemon
            os.execvp(sys.executable, daemon_args)
            sys.exit(0)
        else:
            # 父进程：等待 daemon 启动
            for _ in range(50):  # 最多等 5 秒
                time.sleep(0.1)
                if os.path.exists(DAEMON_SOCKET):
                    return True
            # 超时，检查 daemon 是否还在运行
            try:
                wpid, status = os.waitpid(pid, os.WNOHANG)
                if wpid == pid:
                    # daemon 已退出
                    return False
            except ChildProcessError:
                pass
            return False
    except Exception:
        return False


def _daemon_query(lib: str, word: str) -> dict:
    """通过 daemon socket 查询"""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(3.0)  # 连接超时 3s
    try:
        s.connect(DAEMON_SOCKET)
    except Exception:
        s.close()
        return None  # 降级信号

    # 发送请求
    req = json.dumps({"lib": lib, "word": word}) + "\n"
    s.settimeout(5.0)  # 响应超时 5s
    try:
        s.sendall(req.encode("utf-8"))
        # 读取响应
        resp = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            resp += chunk
            if b"\n" in resp:
                # 找到换行，截断
                resp = resp[: resp.index(b"\n")]
                break
            if len(resp) > 1024 * 1024:  # 1MB 上限
                raise ValueError("Response too large")
    except Exception:
        s.close()
        return None  # 降级信号
    finally:
        try:
            s.close()
        except Exception:
            pass

    try:
        result = json.loads(resp.decode("utf-8"))
        if "error" in result:
            return None  # 降级
        return result if result else {}
    except Exception:
        return None  # 降级


# ═══════════════════════════════════════════════
#  4. 控制命令
# ═══════════════════════════════════════════════

def _cmd_stop():
    """停止守护进程"""
    if os.path.exists(DAEMON_PID_FILE):
        try:
            with open(DAEMON_PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)  # SIGTERM
            # 等待退出
            for _ in range(50):
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
            # 清理文件
            for p in [DAEMON_SOCKET, DAEMON_PID_FILE]:
                try:
                    os.unlink(p)
                except OSError:
                    pass
            print("Daemon stopped.")
        except (OSError, ValueError) as e:
            print(f"Stop failed: {e}", file=sys.stderr)
    else:
        print("No daemon running.")


def _cmd_status():
    """查看守护进程状态"""
    if os.path.exists(DAEMON_PID_FILE):
        try:
            with open(DAEMON_PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            print(f"Daemon running: PID {pid}")
            print(f"Socket: {DAEMON_SOCKET}")
            if os.path.exists(DAEMON_LOG):
                with open(DAEMON_LOG) as f:
                    lines = f.read().strip().split("\n")
                    for line in lines[-5:]:
                        print(f"  {line}")
            return
        except OSError:
            print("PID file stale (process gone)")
        except ValueError:
            print("PID file corrupted")
    else:
        print("No daemon running (will auto-start on first query)")


# ═══════════════════════════════════════════════
#  5. 入口
# ═══════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 query_engine.py <word|root|pronounce> <word>", file=sys.stderr)
        print("       python3 query_engine.py daemon", file=sys.stderr)
        print("       python3 query_engine.py stop", file=sys.stderr)
        print("       python3 query_engine.py status", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    # ─── 控制命令 ───
    if cmd == "daemon":
        _daemon_serve()
        return
    if cmd == "stop":
        _cmd_stop()
        return
    if cmd == "status":
        _cmd_status()
        return
    if cmd == "__warmup__":
        # 内部：强制加载所有索引（daemon 预热用）
        from query_utils import get_word_data, get_root_data, get_pronounce_data
        get_word_data("__warmup__")
        get_root_data("__warmup__")
        get_pronounce_data("__warmup__")
        print("Warmup done.")
        return

    # ─── 查询 ───
    lib = cmd  # word / root / pronounce
    if lib not in ("word", "root", "pronounce"):
        print(f"Unknown lib: {lib}. Use: word, root, pronounce", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) < 3:
        print(f"Usage: python3 query_engine.py {lib} <word>", file=sys.stderr)
        sys.exit(1)

    word = sys.argv[2].strip().lower()
    if not word or len(word) > 20:
        print(json.dumps({}, ensure_ascii=False))
        return

    # 尝试 daemon 路径
    try:
        if _ensure_daemon():
            result = _daemon_query(lib, word)
            if result is not None:
                print(json.dumps(result, ensure_ascii=False))
                return
    except Exception:
        pass

    # 降级：直读
    result = _direct_query(lib, word)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
