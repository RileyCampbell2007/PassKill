import hivex
import hivex.hive_types as hive_types
from typing import Dict, Any, List

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

def get_domain_sid(hive: hivex.Hivex) -> bytes:
    key = hive.root()
    for part in ["SAM", "Domains", "Account"]:
        key = hive.node_get_child(key, part)
        if key is None:
            raise Exception("Could not locate domain SID")

    v_id = hive.node_get_value(key, "V")
    _, v_data = hive.value_value(v_id)
    offset = int.from_bytes(v_data[0x38:0x3B], 'little')+0x40
    length = int.from_bytes(v_data[0x3C:0x40], 'little')+4
    return v_data[offset:offset+length]

def build_user_sid(machine_sid: bytes, user_rid) -> bytes:
    if isinstance(user_rid, str):
        user_rid = int(user_rid, 16)

    # Read revision and subauth count
    revision = machine_sid[0]
    subauth_count = machine_sid[1]
    
    # Check if machine_sid has expected size
    expected_len = 8 + subauth_count * 4
    if len(machine_sid) != expected_len:
        raise ValueError("machine_sid has incorrect length")

    # Append new RID
    new_subauth_count = subauth_count + 1
    authority = machine_sid[2:8]
    subauths = machine_sid[8:]

    new_sid = bytes([revision, new_subauth_count]) + authority + subauths + user_rid.to_bytes(4, 'little')
    return new_sid

def get_group_list(hive: hivex.Hivex, domain: str = "Builtin") -> Dict[str, Dict[str, str]]:
    """
    Get list of groups and their RIDs from the SAM hive using the C value.
    
    Args:
        hive: Open hivex hive object
        domain: "Builtin" or "Account" (where the groups are stored)
    
    Returns:
        Dictionary mapping RIDs (hex string) to group names and comments
    """
    groups: Dict[str, Dict[str, str]] = {}

    key_path = ["SAM", "Domains", domain, "Aliases"]
    key = hive.root()
    for part in key_path:
        key = hive.node_get_child(key, part)
        if key is None:
            raise Exception(f"Key not found: {'\\'.join(key_path)}")
    
    group_nodes = hive.node_children(key)
    hex_chars = set("0123456789ABCDEF")

    for group_node in group_nodes:
        group_rid = hive.node_name(group_node).upper()
        if len(group_rid) != 8 or set(group_rid).difference(hex_chars):
            continue

        c_val = hive.node_get_value(group_node, "C")
        if c_val is None:
            continue

        val_type, val_data = hive.value_value(c_val)
        if val_type != hive_types.REG_BINARY or len(val_data) < 0x34:
            continue

        # RID is stored at offset 0x00
        rid_int = int.from_bytes(val_data[0x00:0x04], "little")
        rid = f"{rid_int:08X}"

        # Offsets to name and comment are stored in the header (relative to offset 0x34)
        base = 0x34
        name_offset = int.from_bytes(val_data[0x10:0x14], "little")
        name_length = int.from_bytes(val_data[0x14:0x18], "little")
        comment_offset = int.from_bytes(val_data[0x1C:0x20], "little")
        comment_length = int.from_bytes(val_data[0x20:0x24], "little")

        try:
            group_name = val_data[base + name_offset : base + name_offset + name_length].decode("utf-16le").rstrip("\x00")
        except:
            group_name = "<decode error>"

        try:
            group_comment = val_data[base + comment_offset : base + comment_offset + comment_length].decode("utf-16le").rstrip("\x00")
        except:
            group_comment = ""

        groups[rid] = {
            "groupname": group_name,
            "comment": group_comment
        }

    return groups

def get_group_members(hive: hivex.Hivex, rid: str, domain: str = "Builtin") -> List[str]:
    """
    Get list of member user RIDs from a group's C value.
    
    Args:
        hive: Open hivex hive object
        rid: Group RID as 8-character hex string (e.g., "00000220")
        domain: Either "Builtin" or "Account"
    
    Returns:
        List of member RIDs as 8-character uppercase hex strings
    """
    key_path = ["SAM", "Domains", domain, "Aliases", rid.upper()]
    key = hive.root()
    for part in key_path:
        key = hive.node_get_child(key, part)
        if key is None:
            raise Exception(f"Key not found: {'\\'.join(key_path)}")

    c_val = hive.node_get_value(key, "C")
    if c_val is None:
        raise Exception("C value not found in group RID node.")

    val_type, val_data = hive.value_value(c_val)
    if val_type != hive_types.REG_BINARY or len(val_data) < 0x34:
        raise Exception("C value is malformed or too short.")

    base = 0x34
    members_ofs = int.from_bytes(val_data[0x28:0x2C], "little")
    members_len = int.from_bytes(val_data[0x2C:0x30], "little")
    member_count = int.from_bytes(val_data[0x30:0x34], "little")

    sid_blob = val_data[base + members_ofs : base + members_ofs + members_len]
    rids = []
    i = 0
    while i < len(sid_blob):
        revision = sid_blob[i]
        subauth_count = sid_blob[i + 1]
        sid_len = 8 + subauth_count * 4
        if sid_len > len(sid_blob) - i:
            break  # avoid overflow on malformed blobs

        last_rid = int.from_bytes(sid_blob[i + 8 + 4 * (subauth_count - 1) : i + 12 + 4 * (subauth_count - 1)], "little")
        rids.append(f"{last_rid:08X}")
        i += sid_len

    if len(rids) != member_count:
        raise Exception(f"Expected {member_count} members, but parsed {len(rids)}.")

    return rids

def rebuild_group_c_value(original: bytes, new_sids: List[bytes]) -> bytes:
    """
    Safely rebuild a group's C value by copying the original header and only updating the offsets.
    
    Args:
        original: The original C value
        new_sids: List of new member SIDs as bytes
    
    Returns:
        Rebuilt C value as bytes
    """
    val_data = bytearray(original)
    base = 0x34

    # Extract the full original header
    header = bytearray(val_data[:0x34])

    # Offsets and lengths for group name and comment (relative to original layout)
    old_name_ofs = int.from_bytes(header[0x10:0x14], 'little')
    name_len = int.from_bytes(header[0x14:0x18], 'little')
    old_comment_ofs = int.from_bytes(header[0x1C:0x20], 'little')
    comment_len = int.from_bytes(header[0x20:0x24], 'little')

    # Extract the actual UTF-16LE data blocks
    name = val_data[base + old_name_ofs: base + old_name_ofs + name_len]
    comment = val_data[base + old_comment_ofs: base + old_comment_ofs + comment_len]

    # Rebuild layout
    sid_blob = b''.join(new_sids)
    new_members_len = len(sid_blob)
    new_members_count = len(new_sids)

    new_name_ofs = new_members_len
    new_comment_ofs = new_name_ofs + len(name)

    # Patch updated offsets/lengths
    header[0x10:0x14] = new_name_ofs.to_bytes(4, 'little')
    header[0x14:0x18] = len(name).to_bytes(4, 'little')
    header[0x1C:0x20] = new_comment_ofs.to_bytes(4, 'little')
    header[0x20:0x24] = len(comment).to_bytes(4, 'little')
    header[0x28:0x2C] = (0).to_bytes(4, 'little')  # members_ofs is always 0
    header[0x2C:0x30] = new_members_len.to_bytes(4, 'little')
    header[0x30:0x34] = new_members_count.to_bytes(4, 'little')

    return bytes(header + sid_blob + name + comment)

def add_user_to_group(hive: hivex.Hivex, user_rid: str, group_rid: str, domain: str = "Builtin") -> bool:
    key_path = ["SAM", "Domains", domain, "Aliases", group_rid.upper()]
    key = hive.root()
    for part in key_path:
        key = hive.node_get_child(key, part)
        if key is None:
            raise Exception("Key not found: " + "\\".join(key_path))

    c_val = hive.node_get_value(key, "C")
    val_type, val_data = hive.value_value(c_val)
    if val_type != hive_types.REG_BINARY or len(val_data) < 0x34:
        raise Exception("Invalid C value.")

    base = 0x34
    members_ofs = int.from_bytes(val_data[0x28:0x2C], "little")
    members_len = int.from_bytes(val_data[0x2C:0x30], "little")
    sid_blob = val_data[base + members_ofs : base + members_ofs + members_len]

    existing_sids = []
    i = 0
    while i < len(sid_blob):
        count = sid_blob[i + 1]
        length = 8 + 4 * count
        existing_sids.append(sid_blob[i:i+length])
        i += length

    machine_sid = get_domain_sid(hive)
    new_sid = build_user_sid(machine_sid, user_rid)
    if new_sid in existing_sids:
        return False

    existing_sids.append(new_sid)
    new_blob = rebuild_group_c_value(val_data, existing_sids)

    hive.node_set_value(key, {
        "key": "C",
        "t": val_type,
        "value": new_blob
    })
    return True

def remove_user_from_group(hive: hivex.Hivex, user_rid: str, group_rid: str, domain: str = "Builtin") -> bool:
    key_path = ["SAM", "Domains", domain, "Aliases", group_rid.upper()]
    key = hive.root()
    for part in key_path:
        key = hive.node_get_child(key, part)
        if key is None:
            raise Exception("Key not found: " + "\\".join(key_path))

    c_val = hive.node_get_value(key, "C")
    val_type, val_data = hive.value_value(c_val)
    if val_type != hive_types.REG_BINARY or len(val_data) < 0x34:
        raise Exception("Invalid C value.")

    base = 0x34
    members_ofs = int.from_bytes(val_data[0x28:0x2C], "little")
    members_len = int.from_bytes(val_data[0x2C:0x30], "little")
    sid_blob = val_data[base + members_ofs : base + members_ofs + members_len]

    machine_sid = get_domain_sid(hive)
    target_sid = build_user_sid(machine_sid, user_rid)

    new_sids = []
    removed = False
    i = 0
    while i < len(sid_blob):
        count = sid_blob[i + 1]
        length = 8 + 4 * count
        sid = sid_blob[i:i+length]
        if sid != target_sid:
            new_sids.append(sid)
        else:
            removed = True
        i += length

    if not removed:
        return False

    new_blob = rebuild_group_c_value(val_data, new_sids)
    hive.node_set_value(key, {
        "key": "C",
        "t": val_type,
        "value": new_blob
    })
    return True
