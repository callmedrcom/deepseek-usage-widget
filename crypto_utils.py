"""
API Key 加密存储 — 使用 Windows DPAPI (CryptProtectData / CryptUnprotectData)
数据以当前用户身份加密，只有当前用户在当前机器上能解密，无需额外依赖。
"""
import ctypes
import ctypes.wintypes
import base64
import platform

_IS_WINDOWS = platform.system() == "Windows"

if _IS_WINDOWS:
    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), ctypes.c_wchar_p,
        ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
        ctypes.wintypes.DWORD, ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptProtectData.restype = ctypes.c_bool

    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), ctypes.POINTER(ctypes.c_wchar_p),
        ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
        ctypes.wintypes.DWORD, ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptUnprotectData.restype = ctypes.c_bool

    def _blob_from_bytes(data: bytes):
        blob = _DATA_BLOB()
        blob.cbData = len(data)
        buf = ctypes.create_string_buffer(data, len(data))
        blob.pbData = ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))
        return blob

    def _blob_to_bytes(blob) -> bytes:
        if not blob.pbData or blob.cbData == 0:
            return b""
        return ctypes.string_at(blob.pbData, blob.cbData)

    def _local_free(ptr):
        _kernel32.LocalFree(ptr)


def encrypt(plaintext: str) -> str:
    """使用 Windows DPAPI 加密字符串，返回 base64 编码的密文。"""
    if not plaintext:
        return ""
    if not _IS_WINDOWS:
        return _fallback_encrypt(plaintext)

    data_in = _blob_from_bytes(plaintext.encode("utf-8"))
    data_out = _DATA_BLOB()

    ok = _crypt32.CryptProtectData(
        ctypes.byref(data_in),
        "DeepSeekWidget",
        None, None, None,
        0x01,  # CRYPTPROTECT_UI_FORBIDDEN
        ctypes.byref(data_out),
    )
    if not ok:
        raise OSError("CryptProtectData failed")

    encrypted = _blob_to_bytes(data_out)
    _local_free(data_out.pbData)
    return base64.urlsafe_b64encode(encrypted).decode("ascii")


def decrypt(encoded: str) -> str:
    """解密由 encrypt() 生成的 base64 密文，返回原始字符串。"""
    if not encoded:
        return ""
    if not _IS_WINDOWS:
        return _fallback_decrypt(encoded)

    try:
        encrypted = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except Exception:
        return encoded

    data_in = _blob_from_bytes(encrypted)
    data_out = _DATA_BLOB()

    ok = _crypt32.CryptUnprotectData(
        ctypes.byref(data_in),
        None, None, None, None,
        0x01,
        ctypes.byref(data_out),
    )
    if not ok:
        return encoded

    decrypted = _blob_to_bytes(data_out)
    _local_free(data_out.pbData)
    return decrypted.decode("utf-8")


# ── 非 Windows 回退方案 ──

import hashlib
import os


def _machine_id():
    try:
        import uuid
        return str(uuid.getnode())
    except Exception:
        return platform.node() + str(os.cpu_count())


def _fallback_key():
    return hashlib.sha256(f"deepseek_widget_{_machine_id()}".encode()).digest()


def _fallback_encrypt(plaintext: str) -> str:
    data = plaintext.encode("utf-8")
    key = _fallback_key()
    encrypted = bytes(a ^ key[i % len(key)] for i, a in enumerate(data))
    return base64.urlsafe_b64encode(encrypted).decode("ascii")


def _fallback_decrypt(encoded: str) -> str:
    try:
        encrypted = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except Exception:
        return encoded
    key = _fallback_key()
    decrypted = bytes(a ^ key[i % len(key)] for i, a in enumerate(encrypted))
    return decrypted.decode("utf-8")
