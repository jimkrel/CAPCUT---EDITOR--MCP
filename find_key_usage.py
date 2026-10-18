import pathlib
import struct

dll_path = pathlib.Path(r'C:\Users\jinnr\AppData\Local\CapCut\Apps\9.6.0.4097\VECreator.dll')
data = dll_path.read_bytes()

# Find the string offset
str_target = b'draft_unconventional_path_cannot_open\x00'
str_pos = data.find(str_target)

# We saw earlier that there is a pointer at 0x9AD43D8 in a table
# Let's find any code that uses this table or searches for draft_unconventional_path_cannot_open
# Let's search for the RVA of the string: 0x9BBDDC0
# In 64-bit code, it could be loaded via:
# mov rdx, [table_entry]
# or via CRC32/hash of the string!
# Let's check if CapCut uses hash/crc of string keys for i18n!
# Common hashes: fnv1a, crc32, djb2, murmur3
import binascii

s_bytes = b'draft_unconventional_path_cannot_open'
crc = binascii.crc32(s_bytes)
print(f'CRC32: 0x{crc:08X}')

# Let's search for crc32 in .text section
pe_offset = struct.unpack_from('<I', data, 0x3C)[0]
opt_hdr_size = struct.unpack_from('<H', data, pe_offset + 4 + 16)[0]
sec_table = pe_offset + 24 + opt_hdr_size
num_sections = struct.unpack_from('<H', data, pe_offset + 4 + 2)[0]

text_sec = None
for i in range(num_sections):
    sec = sec_table + i * 40
    name = data[sec:sec+8].strip(b'\x00').decode('latin1')
    v_size, v_addr, r_size, r_addr = struct.unpack_from('<IIII', data, sec + 8)
    if name == '.text':
        text_sec = (r_addr, r_size, v_addr)
        break

r_addr, r_size, v_addr = text_sec
b_crc = struct.pack('<I', crc)
crc_matches = []
p = r_addr
while True:
    pos = data.find(b_crc, p, r_addr + r_size)
    if pos == -1:
        break
    crc_matches.append(pos)
    p = pos + 1

print('CRC32 matches in .text:', [hex(x) for x in crc_matches])
