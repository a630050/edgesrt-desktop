"""
音訊裝置管理模組 (Audio Manager)
負責偵測 Windows 系統的錄音裝置端點，維護使用者自訂別名，並提供一鍵切換預設錄音端點的功能。
"""

import os
import sys
import json
import logging
import subprocess
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
import ctypes
from ctypes import wintypes, c_wchar_p, byref
import comtypes
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT, client

logger = logging.getLogger("AudioManager")

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, '_MEIPASS', APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

SVV_EXE = os.path.join(BUNDLE_DIR, "bin", "SoundVolumeView.exe")
_appdata_dir = os.environ.get("EDGESRT_APPDATA_DIR", os.path.join(APP_DIR, "_appdata"))
SETTINGS_FILE = os.path.join(_appdata_dir, "audio_sources.json")

CLSID_MMDeviceEnumerator = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
IID_IMMDeviceEnumerator = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
IID_IMMDevice = GUID('{D666063F-1587-4E43-81F1-B948E807363F}')
IID_IMMDeviceCollection = GUID('{0BD7A1BE-7A1A-4465-A1BB-270FA036E41E}')
IID_IPropertyStore = GUID('{886d8eeb-8cf2-4446-8d02-cdba1dbdcf99}')

class PROPERTYKEY(ctypes.Structure):
    _fields_ = [('fmtid', GUID), ('pid', wintypes.DWORD)]

PKEY_Device_FriendlyName = PROPERTYKEY(GUID('{a45c254e-df1c-4efd-8020-67d146a850e0}'), 14)

try:
    propsys = ctypes.windll.propsys
    PropVariantToStringAlloc = propsys.PropVariantToStringAlloc
    PropVariantToStringAlloc.restype = HRESULT
except Exception as e:
    PropVariantToStringAlloc = None
    logger.warning(f"propsys.dll 載入失敗: {e}")

class IPropertyStore(IUnknown):
    _iid_ = IID_IPropertyStore
    _methods_ = [
        COMMETHOD([], HRESULT, 'GetCount'),
        COMMETHOD([], HRESULT, 'GetAt'),
        COMMETHOD([], HRESULT, 'GetValue', (['in'], ctypes.POINTER(PROPERTYKEY), 'key'), (['out'], ctypes.c_char * 24, 'pv')),
    ]

class IMMDevice(IUnknown):
    _iid_ = IID_IMMDevice
    _methods_ = [
        COMMETHOD([], HRESULT, 'Activate'),
        COMMETHOD([], HRESULT, 'OpenPropertyStore', (['in'], wintypes.DWORD, 'stgmAccess'), (['out'], ctypes.POINTER(ctypes.POINTER(IPropertyStore)), 'ppProperties')),
        COMMETHOD([], HRESULT, 'GetId', (['out'], ctypes.POINTER(c_wchar_p), 'ppstrId')),
        COMMETHOD([], HRESULT, 'GetState', (['out'], ctypes.POINTER(wintypes.DWORD), 'pdwState')),
    ]

DEVICE_STATE_ACTIVE = 0x1
DEVICE_STATE_DISABLED = 0x2
DEVICE_STATE_NOTPRESENT = 0x4
DEVICE_STATE_UNPLUGGED = 0x8

class IMMDeviceCollection(IUnknown):
    _iid_ = IID_IMMDeviceCollection
    _methods_ = [
        COMMETHOD([], HRESULT, 'GetCount', (['out'], ctypes.POINTER(ctypes.c_uint), 'pcDevices')),
        COMMETHOD([], HRESULT, 'Item', (['in'], ctypes.c_uint, 'nDevice'), (['out'], ctypes.POINTER(ctypes.POINTER(IMMDevice)), 'ppDevice')),
    ]

class IMMDeviceEnumerator(IUnknown):
    _iid_ = IID_IMMDeviceEnumerator
    _methods_ = [
        COMMETHOD([], HRESULT, 'EnumAudioEndpoints', (['in'], wintypes.DWORD, 'dataFlow'), (['in'], wintypes.DWORD, 'dwStateMask'), (['out'], ctypes.POINTER(ctypes.POINTER(IMMDeviceCollection)), 'ppDevices')),
        COMMETHOD([], HRESULT, 'GetDefaultAudioEndpoint', (['in'], wintypes.DWORD, 'dataFlow'), (['in'], wintypes.DWORD, 'role'), (['out'], ctypes.POINTER(ctypes.POINTER(IMMDevice)), 'ppEndpoint')),
    ]


@dataclass
class AudioDeviceInfo:
    id: str                  # 唯一端點 ID
    name: str                # 實體裝置名稱
    alias: str               # 自訂別名
    show_in_topbar: bool     # 是否顯示在頂部快捷切換列
    is_default: bool = False # 是否為目前預設裝置


class AudioManager:
    """音訊輸入端點掃描、別名管理與預設裝置切換器"""

    def __init__(self):
        self._configs: Dict[str, Dict] = self._load_configs()

    def _load_configs(self) -> Dict[str, Dict]:
        """從 JSON 檔案載入裝置別名與設定"""
        if os.path.isfile(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"讀取音訊設定檔失敗: {e}")
        return {}

    def save_configs(self, device_list: List[AudioDeviceInfo]):
        """儲存裝置別名與設定到 JSON 檔案"""
        data = {}
        for dev in device_list:
            data[dev.id] = {
                "alias": dev.alias,
                "show_in_topbar": dev.show_in_topbar,
                "name": dev.name
            }
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._configs = data
        except Exception as e:
            logger.error(f"寫入音訊設定檔失敗: {e}")

    def get_current_default_device_id(self) -> Optional[str]:
        """取得目前 Windows 預設錄音端點 ID"""
        try:
            comtypes.CoInitialize()
            enumerator = client.CreateObject(CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator)
            dev = enumerator.GetDefaultAudioEndpoint(1, 0)
            return dev.GetId()
        except Exception as e:
            logger.error(f"取得預設音訊輸入裝置失敗: {e}")
            return None
        finally:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass

    def list_capture_devices(self) -> List[AudioDeviceInfo]:
        """掃描 Windows 作用中音訊輸入裝置，並合併自訂別名設定"""
        devices = []
        try:
            comtypes.CoInitialize()
            enumerator = client.CreateObject(CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator)
            collection = enumerator.EnumAudioEndpoints(1, 1)
            count = collection.GetCount()
            default_id = self.get_current_default_device_id()

            for i in range(count):
                dev = collection.Item(i)
                dev_id = dev.GetId()
                props = dev.OpenPropertyStore(0)
                pv = props.GetValue(byref(PKEY_Device_FriendlyName))
                
                dev_name = f"Audio Device {i+1}"
                if PropVariantToStringAlloc:
                    pStr = c_wchar_p()
                    PropVariantToStringAlloc(byref(pv), byref(pStr))
                    if pStr.value:
                        dev_name = pStr.value

                saved = self._configs.get(dev_id, {})
                alias = saved.get("alias", "")
                if not alias:
                    lower_name = dev_name.lower()
                    # 優先權由高到低：USB > 線路輸入(有線) > 立體聲混音(電腦) > 電話類 > 一般麥克風
                    if "usb" in lower_name:
                        alias = "🎤 USB麥克風"
                    elif any(k in dev_name for k in ["線路輸入", "线路输入"]) or \
                         any(k in lower_name for k in ["line in", "line-in"]):
                        alias = "🔌 有線麥克風"
                    elif any(k in dev_name or k in lower_name for k in ["立體聲混音", "立体声混音", "stereo mix", "virtual", "cable", "wave"]):
                        alias = "💻 電腦聲音"
                    elif any(k in dev_name or k in lower_name for k in ["wo mic", "音訊輸入", "音源輸入", "電話", "通話", "phone"]):
                        alias = "📞 電話聲音"
                    elif any(k in dev_name or k in lower_name for k in ["麥克風", "麦克风", "mic", "realtek", "array", "headset"]):
                        alias = "🎤 USB麥克風"
                    else:
                        alias = dev_name

                show_in_topbar = saved.get("show_in_topbar", True)
                is_default = (dev_id == default_id)

                devices.append(AudioDeviceInfo(
                    id=dev_id,
                    name=dev_name,
                    alias=alias,
                    show_in_topbar=show_in_topbar,
                    is_default=is_default
                ))
        except Exception as e:
            logger.error(f"掃描音訊輸入端點失敗: {e}")
        finally:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass

        return devices

    def ensure_stereo_mix_enabled(self) -> List[str]:
        """
        很多電腦的「立體聲混音 / Stereo Mix」錄音裝置預設是停用狀態（Windows
        不會顯示在一般裝置清單，也偵測不到），導致擷取電腦播放聲音的功能形同
        不存在。啟動時掃描一次（含停用裝置），找到名稱符合的就用 SoundVolumeView
        直接啟用。這是 Windows 裝置層級的設定，不是本程式的執行期狀態，關閉
        程式後也會維持啟用，不需要、也不會自動還原。
        回傳這次實際被啟用的裝置名稱清單（沒有動作就是空清單）。
        """
        enabled = []
        if not os.path.isfile(SVV_EXE):
            logger.warning(f"找不到 SoundVolumeView 工具，無法自動啟用立體聲混音: {SVV_EXE}")
            return enabled

        try:
            comtypes.CoInitialize()
            enumerator = client.CreateObject(CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator)
            # dataFlow=1 (eCapture)，dwStateMask 同時含 ACTIVE 與 DISABLED 才能掃到被停用的裝置
            collection = enumerator.EnumAudioEndpoints(1, DEVICE_STATE_ACTIVE | DEVICE_STATE_DISABLED)
            count = collection.GetCount()

            for i in range(count):
                dev = collection.Item(i)
                state = dev.GetState()
                if state != DEVICE_STATE_DISABLED:
                    continue

                dev_id = dev.GetId()
                props = dev.OpenPropertyStore(0)
                pv = props.GetValue(byref(PKEY_Device_FriendlyName))
                dev_name = ""
                if PropVariantToStringAlloc:
                    pStr = c_wchar_p()
                    PropVariantToStringAlloc(byref(pv), byref(pStr))
                    if pStr.value:
                        dev_name = pStr.value

                lower_name = dev_name.lower()
                if not any(k in dev_name or k in lower_name for k in ["立體聲混音", "立体声混音", "stereo mix"]):
                    continue

                cmd = [SVV_EXE, "/Enable", dev_id]
                res = subprocess.run(cmd, capture_output=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                if res.returncode == 0:
                    logger.info(f"已自動啟用停用中的立體聲混音裝置: {dev_name}")
                    enabled.append(dev_name)
                else:
                    logger.warning(f"嘗試啟用立體聲混音裝置失敗 (returncode={res.returncode}): {dev_name}")
        except Exception as e:
            logger.error(f"掃描/啟用立體聲混音裝置失敗: {e}")
        finally:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass

        return enabled

    def set_default_device(self, device_id: str) -> bool:
        """使用 SoundVolumeView 將指定 ID 設為 Windows 預設錄音端點"""
        if not os.path.isfile(SVV_EXE):
            logger.error(f"找不到 SoundVolumeView 工具: {SVV_EXE}")
            return False

        try:
            cmd = [SVV_EXE, "/SetDefault", device_id, "all"]
            res = subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if res.returncode == 0:
                logger.info(f"成功將預設音訊輸入端點切換至: {device_id}")
                return True
            else:
                logger.error(f"切換音訊端點失敗，返回碼: {res.returncode}")
                return False
        except Exception as e:
            logger.error(f"執行音訊端點切換命令異常: {e}")
            return False
