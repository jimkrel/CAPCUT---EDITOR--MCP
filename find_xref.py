import pathlib
import struct

dll_path = pathlib.Path(r'C:\Users\jinnr\AppData\Local\CapCut\Apps\9.6.0.4097\VECreator.dll')
data = dll_path.read_bytes()

key = b'draft_unconventional_path_cannot_open\x00'
key_offset = data.find(key)
print('Key offset:', key_offset)

# In 64-bit PE, find RVA and image base
# e_lfanew
pe_offset = struct.unpack_from('<I', data, 0x3C)[0]
# OptionalHeader ImageBase at pe_offset + 24 + 24
image_base = struct.unpack_from('<Q', data, pe_offset + 24 + 24)[0]
print(f'ImageBase: 0x{image_base:X}')

# Find section for key_offset
num_sections = struct.unpack_from('<H', data, pe_offset + 4 + 2)[0]
opt_hdr_size = struct.unpack_from('<H', data, pe_offset + 4 + 16)[0]
sec_table = pe_offset + 24 + opt_hdr_size

key_rva = None
for i in range(num_sections):
    sec = sec_table + i * 40
    name = data[sec:sec+8].strip(b'\x00').decode('latin1')
    v_size, v_addr, r_size, r_addr = struct.unpack_from('<IIII', data, sec + 8)
    if r_addr <= key_offset < r_addr + r_size:
        key_rva = v_addr + (key_offset - r_addr)
        print(f'Key in section {name}, RVA: 0x{key_rva:X}')
        break

if key_rva:
    key_va = image_base + key_rva
    b_va = struct.pack('<Q', key_va)
    # Search for pointer
    ptr_matches = []
    p = 0
    while True:
        pos = data.find(b_va, p)
        if pos == -1:
            break
        ptr_matches.append(pos)
        p = pos + 1
    print('Pointer references:', len(ptr_matches))
    for pm in ptr_matches:
        print(f'  at raw offset 0x{pm:X}')
