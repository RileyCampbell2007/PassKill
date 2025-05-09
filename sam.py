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