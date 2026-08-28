"""
Edge 擷取器背景通信服務 (Capture Server)
啟動本機 HTTP + WebSocket 服務，並在背景靜默啟動 Microsoft Edge 瀏覽器作為語音辨識引擎。
透過 WebSocket 毫秒級雙向收發轉錄文字與控制指令。
"""

import os
import sys
import json
import time
import shutil
import socket
import logging
import asyncio
import threading
import subprocess
from typing import Callable, Optional, Set
from aiohttp import web

logger = logging.getLogger("CaptureServer")

# 每次啟動前可安全清除的 Edge profile 快取子路徑：皆為 Chromium 用得到時會自動
# 重新生成的快取（GPU shader、HTTP/JS 快取、遙測記錄），刪除不影響任何功能。
# 刻意不列入 Speech Recognition / EdgeLanguageDetectionModel / component_crx_cache /
# Preferences 等——這些動了會導致語音辨識元件遺失，重演過去的問題。
_SAFE_TO_TRIM_CACHE_PATHS = [
    "GrShaderCache",
    "ShaderCache",
    "BrowserMetrics",
    "BrowserMetrics-spare.pma",
    os.path.join("Default", "Cache"),
    os.path.join("Default", "Code Cache"),
    os.path.join("Default", "GPUCache"),
    os.path.join("Default", "DawnWebGPUCache"),
    os.path.join("Default", "DawnGraphiteCache"),
]

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, '_MEIPASS', APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

CAPTURER_DIR = os.path.join(BUNDLE_DIR, "capturer")

def find_free_port(start=8100, end=8150) -> int:
    """尋找可用連接埠"""
    for port in range(start, end + 1):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            return port
        except OSError:
            s.close()
            continue
    raise RuntimeError(f"無法在連接埠範圍 {start}~{end} 找到可用的 TCP 連接埠")


class CaptureServer:
    """HTTP 靜態檔案服務 + WebSocket 語音轉錄串流伺服端"""

    def __init__(self,
                 on_interim_text: Optional[Callable[[str], None]] = None,
                 on_final_text: Optional[Callable[[str], None]] = None,
                 on_status_change: Optional[Callable[[str], None]] = None,
                 on_volume: Optional[Callable[[int], None]] = None):
        self.port = find_free_port()
        self.on_interim_text = on_interim_text
        self.on_final_text = on_final_text
        self.on_status_change = on_status_change
        self.on_volume = on_volume

        self._active_clients: Set[web.WebSocketResponse] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._edge_proc: Optional[subprocess.Popen] = None
        self._edge_hidden = True
        self._last_edge_launch_at = 0.0
        self.running = False

    async def _handle_index(self, request):
        """返回語音辨識擷取網頁"""
        html_path = os.path.join(CAPTURER_DIR, "index.html")
        return web.FileResponse(html_path)

    async def _handle_ws(self, request):
        """處理 WebSocket 連線"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._active_clients.add(ws)
        logger.info("Edge 語音擷取器 WebSocket 客戶端已建立連線")
        if self.on_status_change:
            self.on_status_change("已連線 Edge 語音引擎")

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        event = data.get("event")
                        text = data.get("text", "")

                        if event == "interim" and self.on_interim_text:
                            self.on_interim_text(text)
                        elif event == "final" and self.on_final_text:
                            self.on_final_text(text)
                        elif event == "volume" and self.on_volume:
                            self.on_volume(int(data.get("volume", 0)))
                        elif event == "speech_status" and self.on_status_change:
                            self.on_status_change(f"Edge 語音狀態: {data.get('status', '')}")
                        elif event == "error" and self.on_status_change:
                            err_val = str(data.get("error", "")).strip()
                            if err_val and err_val != "aborted":
                                self.on_status_change(f"語音辨識提示: {err_val}")
                    except Exception as e:
                        logger.error(f"解析 WebSocket 訊息異常: {e}")
                elif msg.type == web.WSMsgType.ERROR:
                    logger.warning(f"WebSocket 異常中斷: {ws.exception()}")
        finally:
            self._active_clients.discard(ws)
            if self.on_status_change and not self._active_clients:
                self.on_status_change("Edge 語音引擎已中斷連線")
        return ws

    def _find_edge_path(self) -> Optional[str]:
        """搜尋系統中的 Microsoft Edge 路徑"""
        edge_paths = [
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        for p in edge_paths:
            if os.path.isfile(p):
                return p
        return None

    def _get_edge_user_data_dir(self) -> str:
        _appdata_dir = os.environ.get("EDGESRT_APPDATA_DIR", os.path.join(APP_DIR, "_appdata"))
        return os.path.join(_appdata_dir, "edge_profile")

    def _terminate_tracked_edge(self):
        """Terminate the Edge process tree started by this CaptureServer instance."""
        if not self._edge_proc:
            return

        pid = self._edge_proc.pid
        if os.name == 'nt':
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as e:
                logger.warning(f"終止目前 Edge process tree 失敗 (PID={pid}): {e}")
        try:
            self._edge_proc.terminate()
            self._edge_proc.wait(timeout=1)
        except Exception:
            try:
                self._edge_proc.kill()
            except Exception:
                pass
        self._edge_proc = None

    def _suppress_crash_restore(self, user_data_dir: str):
        """
        本工具每次結束/重啟都用 taskkill 強殺 Edge 進程，Chromium profile 會被標記為
        「未正常關閉」，下次啟動時可能跳出「還原頁面」提示視窗。啟動前把 Preferences
        的 exit_type 改回 Normal，避免這個提示視窗造成畫面閃現。
        """
        prefs_path = os.path.join(user_data_dir, "Default", "Preferences")
        if not os.path.isfile(prefs_path):
            return
        try:
            with open(prefs_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
            profile = prefs.setdefault("profile", {})
            if profile.get("exit_type") != "Normal" or not profile.get("exited_cleanly", True):
                profile["exit_type"] = "Normal"
                profile["exited_cleanly"] = True
                with open(prefs_path, "w", encoding="utf-8") as f:
                    json.dump(prefs, f)
        except Exception as e:
            logger.warning(f"清除 Edge profile 異常關閉標記失敗: {e}")

    def _trim_profile_cache(self, user_data_dir: str):
        """
        每次啟動前清掉可安全重新生成的快取資料夾，避免長期使用下 profile
        持續肥大。只刪 _SAFE_TO_TRIM_CACHE_PATHS 列出的純快取項目，語音辨識
        元件與設定檔一律不動。
        """
        trimmed = []
        for rel in _SAFE_TO_TRIM_CACHE_PATHS:
            path = os.path.join(user_data_dir, rel)
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    trimmed.append(rel)
                elif os.path.isfile(path):
                    os.remove(path)
                    trimmed.append(rel)
            except Exception as e:
                logger.warning(f"清除 Edge 快取 {rel} 失敗: {e}")
        if trimmed:
            logger.info(f"已清除 Edge profile 快取: {', '.join(trimmed)}")

    def _kill_orphaned_edge(self, user_data_dir: str):
        """
        清除上一次執行殘留的孤兒 Edge 進程（例如上次 App 被強制關閉，未經過
        stop() 清理，導致 Edge 進程樹留在背景並鎖住 profile 資料夾）。
        用進程指令列精準比對「本工具自己的 --user-data-dir 路徑」，只會清掉
        這個工具自己啟動過的 Edge，不會影響使用者平常在用的 Edge 瀏覽器。
        """
        if os.name != 'nt':
            return
        try:
            needle = user_data_dir.replace("'", "''")
            ps_cmd = (
                "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'msedge.exe' -and "
                "$_.CommandLine -like '*" + needle + "*' } | Select-Object -ExpandProperty ProcessId"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=6,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            pids = [p.strip() for p in result.stdout.splitlines() if p.strip().isdigit()]
            for pid in pids:
                subprocess.run(["taskkill", "/F", "/T", "/PID", pid],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
                                creationflags=subprocess.CREATE_NO_WINDOW)
            if pids:
                logger.info(f"啟動前清除 {len(pids)} 個殘留孤兒 Edge 進程 (PID: {', '.join(pids)})")
        except Exception as e:
            logger.warning(f"清除孤兒 Edge 進程異常: {e}")

    def launch_edge(self, hidden=True, force=False):
        """啟動 Edge 背景語音擷取器"""
        edge_exe = self._find_edge_path()
        if not edge_exe:
            logger.error("系統未找到 Microsoft Edge 安裝路徑")
            if self.on_status_change:
                self.on_status_change("未偵測到 Edge 瀏覽器，請先安裝 Edge")
            return

        now = time.monotonic()
        if not force and now - self._last_edge_launch_at < 3:
            logger.info("略過過於密集的 Edge 重啟請求")
            return

        self._terminate_tracked_edge()

        user_data_dir = self._get_edge_user_data_dir()
        self._kill_orphaned_edge(user_data_dir)
        os.makedirs(user_data_dir, exist_ok=True)
        self._trim_profile_cache(user_data_dir)
        self._suppress_crash_restore(user_data_dir)

        url = f"http://127.0.0.1:{self.port}/"
        args = [
            edge_exe,
            f"--app={url}",
            f"--user-data-dir={user_data_dir}",
            "--use-fake-ui-for-media-stream",  # 自動允許麥克風權限
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-translate",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=CalculateNativeWinOcclusion",
            "--disable-session-crashed-bubble",
            "--hide-crash-restore-bubble",
            "--autoplay-policy=no-user-gesture-required",
            "--window-size=360,260",
            # 這個 profile 只用來跑一個本機語音辨識頁面，不需要 Edge 內建的購物/
            # 錢包/優惠券/側邊欄等 UI 型元件擴充功能，關掉可避免持續下載累積。
            # 注意：--disable-component-update / --disable-background-networking
            # 已移除——實測會連帶擋掉 Web Speech API 需要的語音辨識元件/網路連線，
            # 導致完全無法轉錄，兩害相權，保留轉錄功能優先。
            "--disable-component-extensions-with-background-pages",
            "--disable-sync",
            "--disable-default-apps",
            "--disable-client-side-phishing-detection",
        ]

        try:
            self._edge_proc = subprocess.Popen(args)
            self._last_edge_launch_at = time.monotonic()
            logger.info(f"Edge 擷取器已啟動: PID={self._edge_proc.pid}, URL={url}")
            if hidden and os.name == 'nt':
                threading.Thread(target=self._hide_edge_window, daemon=True).start()
        except Exception as e:
            logger.error(f"啟動 Edge 擷取器失敗: {e}")

    def _hide_edge_window(self):
        """在 Windows 下隱藏 Edge 擷取器視窗（PID 精準匹配 + 標題兜底）"""
        if not self._edge_proc:
            return
        target_pid = self._edge_proc.pid
        # NOTE: Chromium 啟動後可能將視窗委派給子進程，導致 Popen PID 與視窗 PID 不同
        # 因此先嘗試 PID 匹配，若失敗則以 HTML <title> 作為兜底匹配
        try:
            import win32gui
            import win32con
            import win32process

            for attempt in range(40):
                time.sleep(0.25)
                found = False

                def _enum_cb(hwnd, _):
                    nonlocal found
                    if found:
                        return False
                    if not win32gui.IsWindowVisible(hwnd):
                        return True
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    title = win32gui.GetWindowText(hwnd)
                    # 策略一：精準 PID 匹配（進程未委派時命中）
                    # 策略二：標題匹配（進程已委派給子進程時兜底）
                    if pid == target_pid or title == "Edge 語音轉錄背景擷取器":
                        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                        logger.info(f"已隱藏 Edge 擷取器視窗 (PID={pid}, HWND={hwnd}, Title='{title}')")
                        found = True
                        return False
                    return True

                win32gui.EnumWindows(_enum_cb, None)
                if found:
                    break
        except Exception as e:
            logger.warning(f"隱藏 Edge 擷取器視窗異常: {e}")

    async def _edge_watchdog_loop(self):
        """守護 Edge 背景程序：僅在 WebSocket 斷線且長達 16 秒以上無重連時才重新拉起"""
        disconnected_time = 0
        try:
            while self.running:
                await asyncio.sleep(4)
                if not self.running:
                    break
                # 若已有活躍的 WebSocket 連線，代表 Edge 運作良好，不需重啟
                if not self._active_clients:
                    disconnected_time += 4
                    if disconnected_time >= 16:
                        logger.warning("偵測到 Edge 語音引擎斷線超過 16 秒，正在重新拉起 Edge...")
                        disconnected_time = 0
                        self.launch_edge(hidden=self._edge_hidden)
                else:
                    disconnected_time = 0
        except asyncio.CancelledError:
            pass

    def send_command(self, command: str, **kwargs):
        """向所有連線的 Edge 擷取器廣播控制指令"""
        if not self._loop or not self._active_clients:
            return

        payload = {"command": command, **kwargs}
        msg_str = json.dumps(payload)

        async def _broadcast():
            for ws in list(self._active_clients):
                try:
                    await ws.send_str(msg_str)
                except Exception as e:
                    logger.warning(f"發送廣播指令失敗: {e}")

        asyncio.run_coroutine_threadsafe(_broadcast(), self._loop)

    def restart_asr(self):
        """通知 Edge 重啟語音辨識（切換音源或手動刷新時調用）"""
        self.send_command("restart")

    def restart_capturer(self):
        """Restart the Edge capturer process so Web Speech rebinds to the current input device."""
        self.launch_edge(hidden=self._edge_hidden, force=True)

    def pause_asr(self):
        """暫停語音辨識"""
        self.send_command("stop")

    def resume_asr(self):
        """恢復語音辨識"""
        self.send_command("start")

    def set_language(self, lang: str):
        """切換語音辨識語言 (如 zh-TW, zh-CN, en-US, ja-JP)"""
        self.send_command("setLang", lang=lang)

    def start(self, hidden_edge=True):
        """啟動背景服務執行緒"""
        if self.running:
            return
        self.running = True
        self._edge_hidden = hidden_edge

        def _run_server():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            self._app = web.Application()
            self._app.router.add_get('/', self._handle_index)
            self._app.router.add_get('/ws', self._handle_ws)
            self._app.router.add_static('/', CAPTURER_DIR)

            self._runner = web.AppRunner(self._app)
            self._loop.run_until_complete(self._runner.setup())
            self._site = web.TCPSite(self._runner, '127.0.0.1', self.port)
            self._loop.run_until_complete(self._site.start())

            logger.info(f"Capture Server 運行於: http://127.0.0.1:{self.port}")
            self.launch_edge(hidden=hidden_edge)

            # 啟動 Edge 崩潰守護協程
            self._watchdog_task = self._loop.create_task(self._edge_watchdog_loop())

            try:
                self._loop.run_forever()
            finally:
                # 徹底優雅清理 aiohttp site 與 AppRunner
                try:
                    if hasattr(self, '_watchdog_task') and self._watchdog_task and not self._watchdog_task.done():
                        self._watchdog_task.cancel()
                    if self._site:
                        self._loop.run_until_complete(self._site.stop())
                    if self._runner:
                        self._loop.run_until_complete(self._runner.cleanup())
                except Exception as e:
                    logger.warning(f"清理 aiohttp 伺服器異常: {e}")
                self._loop.close()

        self._thread = threading.Thread(target=_run_server, daemon=True)
        self._thread.start()

    def stop(self):
        """停止服務並精準清理 Edge 背景程序樹"""
        self.running = False
        if self._edge_proc:
            pid = self._edge_proc.pid
            if os.name == 'nt':
                # 使用 taskkill /F /T 精准回收該進程樹（只殺這個 pid 及其衍生子進程，不影響使用者的日常 Edge）
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                except Exception:
                    pass
            try:
                self._edge_proc.terminate()
                self._edge_proc.wait(timeout=1)
            except Exception:
                try:
                    self._edge_proc.kill()
                except Exception:
                    pass
            self._edge_proc = None

        user_data_dir = self._get_edge_user_data_dir()
        self._kill_orphaned_edge(user_data_dir)

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    srv = CaptureServer(
        on_interim_text=lambda t: print(f"[即時文字] {t}"),
        on_final_text=lambda t: print(f"[確認文字] {t}"),
        on_status_change=lambda s: print(f"[狀態更新] {s}")
    )
    srv.start(hidden_edge=False)
    print("服務已啟動，按 Ctrl+C 結束...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.stop()
        print("服務已結束")
