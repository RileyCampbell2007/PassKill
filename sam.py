import hivex
import hivex.hive_types as hive_types
from typing import Dict, Any

def get_user_list(hive: hivex.Hivex) -> Dict[str, Dict[str, str]]:
    """
    Get list of users and their RIDs from the SAM hive using the Names key.
    
    Args:
        hive: Open hivex hive object
        
    Returns:
        Dictionary mapping RIDs (strings like '000003E8') to usernames and full names
    """
    users: Dict[str, Dict[str, str]] = {}

    # Navigate to SAM\Domains\Account\Users\Names
    key_path = ["SAM", "Domains", "Account", "Users"]
    key = hive.root()
    
    for part in key_path:
        key = hive.node_get_child(key, part)
        if key is None:
            raise Exception(f"Key not found: {'\\'.join(key_path)}")
    
    # Each subkey under Names is a username
    rid_nodes = hive.node_children(key)
    
    hex_chars = set("0123456789ABCDEF")

    for rid_node in rid_nodes:
        
        rid = hive.node_name(rid_node)
        if len(rid) != 8 or set(rid).difference(hex_chars):
            continue
        
        V = hive.node_get_value(rid_node, "V")
        if V is None:
            continue
            
        V_type, V_data = hive.value_value(V)
        if V_type != hive_types.REG_BINARY:
            continue
        
        username_offset = int.from_bytes(V_data[0x0C:0x0C+4], byteorder='little')
        username_length = int.from_bytes(V_data[0x10:0x10+4], byteorder='little')

        fullname_offset = int.from_bytes(V_data[0x18:0x18+4], byteorder='little')
        fullname_length = int.from_bytes(V_data[0x1C:0x1C+4], byteorder='little')

        V_data = V_data[0xCC:]

        try: username = V_data[username_offset:username_offset+username_length].decode('utf-16le').replace('\x00','') 
        except: continue
        try: fullname = V_data[fullname_offset:fullname_offset+fullname_length].decode('utf-16le').replace('\x00','').strip()
        except: fullname = ""

        users[rid] = {
            "username": username,
            "fullname": fullname
        }

    return users

def remove_password(hive: hivex.Hivex, user_rid: str) -> bool:
    """
    Remove password for a specific user.
    
    Args:
        hive: Open hivex hive object
        user_rid: User RID (e.g., '000003E8')
        
    Returns:
        True if operation succeeded, False otherwise
    """
    key_path = ["SAM", "Domains", "Account", "Users", user_rid]
    key = hive.root()
    
    for part in key_path:
        key = hive.node_get_child(key, part)
        if key is None:
            raise Exception(f"Key not found: {'\\'.join(key_path)}")
    
    v_value_id = hive.node_get_value(key, "V")
    if v_value_id is None:
        raise Exception("V value not found in user key")

    v_value_type, v_value_data = hive.value_value(v_value_id)
    if v_value_data is None:
        raise Exception("Failed to read V value data")

    v_value_data = bytearray(v_value_data)

    if len(v_value_data) < 0xCC:
        raise Exception("V value is too short to contain valid password fields")

    offsets = [0xA0,0xAC]

    for offset in offsets:
        v_value_data[offset:offset+4] = b"\x00\x00\x00\x00"

    hive.node_set_value(key, {
        "key": "V",
        "t": v_value_type,
        "value": bytes(v_value_data)
    })
    
    return True

def convert_to_local_account(hive: hivex.Hivex, user_rid: str) -> bool:
    """
    Convert a Microsoft account to a local account.
    
    Args:
        hive: Open hivex hive object
        user_rid: User RID (e.g., '000003E8')
        
    Returns:
        True if operation succeeded, False otherwise
    """
    key_path = ["SAM", "Domains", "Account", "Users", user_rid]
    key = hive.root()
    
    for part in key_path:
        key = hive.node_get_child(key, part)
        if key is None:
            raise Exception(f"Key not found: {'\\'.join(key_path)}")

    hive.node_set_value(key, {
        "key": "InternetSID",
        "t": hive_types.REG_BINARY,
        "value": b""
    })

    hive.node_set_value(key, {
        "key": "InternetUID",
        "t": hive_types.REG_BINARY,
        "value": b""
    })

    hive.node_set_value(key, {
        "key": "InternetProviderGUID",
        "t": hive_types.REG_BINARY,
        "value": b"\x00" * 16
    })
    
    return True

class FValue:
    ACB_FLAGS = {
        "ACB_DISABLED":  0x0001,
        "ACB_HOMDIRREQ": 0x0002,
        "ACB_PWNOTREQ":  0x0004,
        "ACB_TEMPDUP":   0x0008,
        "ACB_NORMAL":    0x0010,
        "ACB_MNS":       0x0020,
        "ACB_DOMTRUST":  0x0040,
        "ACB_WSTRUST":   0x0080,
        "ACB_SVRTRUST":  0x0100,
        "ACB_PWNOEXP":   0x0200,
        "ACB_AUTOLOCK":  0x0400,
    }

    def __init__(self, f_data: bytes):
        if len(f_data) < 0x44:
            raise ValueError("F value is too short to contain account flags.")
        self._raw = bytearray(f_data)
        self._flags_offset = 0x38
        self._flags = int.from_bytes(self._raw[self._flags_offset:self._flags_offset + 4], 'little')

    @property
    def flags(self):
        return FFlagDict(self)

    def to_bytes(self) -> bytes:
        return bytes(self._raw)

class FFlagDict:
    def __init__(self, parent: FValue):
        self._parent = parent

    def __getitem__(self, key: str) -> bool:
        bit = FValue.ACB_FLAGS.get(key)
        if bit is None:
            raise KeyError(f"Unknown flag: {key}")
        return bool(self._parent._flags & bit)

    def __setitem__(self, key: str, value: bool):
        bit = FValue.ACB_FLAGS.get(key)
        if bit is None:
            raise KeyError(f"Unknown flag: {key}")
        if value:
            self._parent._flags |= bit
        else:
            self._parent._flags &= ~bit
        self._parent._raw[self._parent._flags_offset:self._parent._flags_offset + 4] = \
            self._parent._flags.to_bytes(4, 'little')

def load_f_value(hive: hivex.Hivex, user_rid: str) -> FValue:
    """
    Load and parse the F value for a user RID into an FValue object.
    """
    key_path = ["SAM", "Domains", "Account", "Users", user_rid]
    key = hive.root()
    for part in key_path:
        key = hive.node_get_child(key, part)
        if key is None:
            raise Exception(f"Key not found: {'\\'.join(key_path)}")

    f_value_id = hive.node_get_value(key, "F")
    if f_value_id is None:
        raise Exception("F value not found in user key")

    f_type, f_data = hive.value_value(f_value_id)
    if f_data is None or f_type != hive_types.REG_BINARY:
        raise Exception("Invalid or missing F value data")

    return FValue(f_data)


def save_f_value(hive: hivex.Hivex, user_rid: str, fval: FValue) -> None:
    """
    Save the modified FValue object back to the registry.
    """
    key_path = ["SAM", "Domains", "Account", "Users", user_rid]
    key = hive.root()
    for part in key_path:
        key = hive.node_get_child(key, part)
        if key is None:
            raise Exception(f"Key not found: {'\\'.join(key_path)}")

    hive.node_set_value(key, {
        "key": "F",
        "t": hive_types.REG_BINARY,
        "value": fval.to_bytes()
    })