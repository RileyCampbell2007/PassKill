import hivex
import hivex.hive_types as hive_types
from typing import Dict, Any

def get_user_list(hive: hivex.Hivex) -> Dict[str, str]:
    """
    Get list of users and their RIDs from the SAM hive using the Names key.
    
    Args:
        hive: Open hivex hive object
        
    Returns:
        Dictionary mapping RIDs (strings like '000003E8') to usernames
    """
    users: Dict[str, str] = {}
    
    try:
        # Navigate to SAM\Domains\Account\Users\Names
        sam_node = hive.node_get_child(hive.root(), "SAM")
        domains_node = hive.node_get_child(sam_node, "Domains")
        account_node = hive.node_get_child(domains_node, "Account")
        users_node = hive.node_get_child(account_node, "Users")
        names_node = hive.node_get_child(users_node, "Names")
        
        if not names_node:
            raise Exception("Names key not found in SAM hive")
        
        # Each subkey under Names is a username
        user_nodes = hive.node_children(names_node)
        for user_node in user_nodes:
            username = hive.node_name(user_node)
            
            # The default value contains the RID in binary form
            default_value_id = hive.node_get_value(user_node, "")
            if default_value_id:
                rid_data, _ = hive.value_value(default_value_id)
                rid_data = rid_data.to_bytes(4, byteorder='little')
                if rid_data and len(rid_data) == 4:  # RID is 4 bytes
                    # Convert little-endian bytes to RID (integer)
                    rid_int = int.from_bytes(rid_data, byteorder='little')
                    # Format as 8-digit hex string (e.g., '000003E8')
                    rid_hex = f"{rid_int:08X}"

                    
                    # Verify the RID exists in the Users directory
                    rid_node = hive.node_get_child(users_node, rid_hex)
                    if rid_node:
                        users[rid_hex] = username
                    else:
                        print(f"Warning: Found user {username} with RID {rid_hex} but no corresponding user key")
    
    except Exception as e:
        print(f"Error getting user list: {e}")
    
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
    try:
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

        data = bytearray(v_value_data)

        if len(data) < 0xCC:
            raise Exception("V value is too short to contain valid password fields")

        data[0xA0:0xA0+2] = b"\x00\x00"
        data[0xAC:0xAC+2] = b"\x00\x00"

        hive.node_set_value(key, {
            "key": "V",
            "t": v_value_type,
            "value": bytes(data)
        })
        
        return True
    except Exception as e:
        print(f"Error removing password: {e}")
        return False

def convert_to_local_account(hive: hivex.Hivex, user_rid: str) -> bool:
    """
    Convert a Microsoft account to a local account.
    
    Args:
        hive: Open hivex hive object
        user_rid: User RID (e.g., '000003E8')
        
    Returns:
        True if operation succeeded, False otherwise
    """
    try:
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
    except Exception as e:
        print(f"Error converting to local account: {e}")
        return False