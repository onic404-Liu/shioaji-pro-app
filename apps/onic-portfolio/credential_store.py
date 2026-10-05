"""Windows Credential Manager. Never stores credentials in project files."""
import ctypes
from ctypes import wintypes
import json
import os


class Credential(ctypes.Structure):
    _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD),
                ('TargetName', wintypes.LPWSTR), ('Comment', wintypes.LPWSTR),
                ('LastWritten', wintypes.FILETIME), ('CredentialBlobSize', wintypes.DWORD),
                ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)),
                ('Persist', wintypes.DWORD), ('AttributeCount', wintypes.DWORD),
                ('Attributes', ctypes.c_void_p), ('TargetAlias', wintypes.LPWSTR),
                ('UserName', wintypes.LPWSTR)]


class Vault:
    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('此保存方式需要 Windows 認證管理員。')
        self.dll = ctypes.WinDLL('advapi32', use_last_error=True)
        self.dll.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        self.dll.CredWriteW.restype = wintypes.BOOL
        self.dll.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                     ctypes.POINTER(ctypes.POINTER(Credential))]
        self.dll.CredReadW.restype = wintypes.BOOL
        self.dll.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self.dll.CredDeleteW.restype = wintypes.BOOL
        self.dll.CredFree.argtypes = [ctypes.c_void_p]
        self.dll.CredFree.restype = None

    @staticmethod
    def target(profile):
        if profile not in ('simulation', 'readonly'):
            raise ValueError('未知金鑰用途。')
        return 'Onic/SinoPac/' + profile

    def read(self, profile):
        pointer = ctypes.POINTER(Credential)()
        if not self.dll.CredReadW(self.target(profile), 1, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == 1168:
                return None
            raise RuntimeError('無法讀取 Windows 認證管理員。')
        try:
            value = json.loads(ctypes.string_at(pointer.contents.CredentialBlob,
                               pointer.contents.CredentialBlobSize).decode('utf-8'))
            return value['key'], value['secret']
        finally:
            self.dll.CredFree(pointer)

    def write(self, profile, key, secret):
        if not key or not secret:
            raise ValueError('請填寫兩組金鑰。')
        blob = json.dumps({'key': key, 'secret': secret}).encode('utf-8')
        if len(blob) > 2560:
            raise ValueError('金鑰長度超出保存上限。')
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        credential = Credential(Type=1, TargetName=self.target(profile),
                                CredentialBlobSize=len(blob), CredentialBlob=buffer,
                                Persist=2, UserName='Shioaji API')
        if not self.dll.CredWriteW(ctypes.byref(credential), 0):
            raise RuntimeError('Windows 認證管理員保存失敗。')

    def delete(self, profile):
        if not self.dll.CredDeleteW(self.target(profile), 1, 0):
            if ctypes.get_last_error() != 1168:
                raise RuntimeError('無法刪除 Windows 保存的金鑰。')

    def saved(self):
        return {p: self.read(p) is not None for p in ('simulation', 'readonly')}
