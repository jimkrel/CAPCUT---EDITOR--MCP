import pathlib
import struct

dll_path = pathlib.Path(r'C:\Users\jinnr\AppData\Local\CapCut\Apps\9.6.0.4097\VECreator.dll')
data = dll_path.read_bytes()

# Find the string offset
str_target = b'draft_unconventional_path_cannot_open\x00'
str_pos = data.find(str_target)
print('String pos:', str_pos)

# PE headers
pe_offset = struct.unpack_from('<I', data, 0x3C)[0]
image_base = struct.unpack_from('<Q', data, pe_offset + 24 + 24)[0]
num_sections = struct.unpack_from('<H', data, pe_offset + 4 + 2)[0]
opt_hdr_size = struct.unpack_from('<H', data, pe_offset + 4 + 16)[0]
sec_table = pe_offset + 24 + opt_hdr_size

def file_offset_to_rva(f_off):
    for i in range(num_sections):
        sec = sec_table + i * 40
        v_size, v_addr, r_size, r_addr = struct.unpack_from('<IIII', data, sec + 8)
        if r_addr <= f_off < r_addr + r_size:
            return v_addr + (f_off - r_addr)
    return None

def rva_to_file_offset(rva):
    for i in range(num_sections):
        sec = sec_table + i * 40
        v_size, v_addr, r_size, r_addr = struct.unpack_from('<IIII', data, sec + 8)
        if v_addr <= rva < v_addr + v_size:
            return r_addr + (rva - v_addr)
    return None

str_rva = file_offset_to_rva(str_pos)
print(f'String RVA: 0x{str_rva:X}')

# Find RIP-relative LEA instructions pointing to str_rva:
# In x86_64: 48 8D ?? [disp32] where next_rip + disp32 == image_base + str_rva
# Or in text section: (rva_inst + len_inst) + disp32 == str_rva -> disp32 = str_rva - (rva_inst + len_inst)
# Let's search all LEA reg, [rip + disp32] in .text section!

text_sec = None
for i in range(num_sections):
    sec = sec_table + i * 40
    name = data[sec:sec+8].strip(b'\x00').decode('latin1')
    v_size, v_addr, r_size, r_addr = struct.unpack_from('<IIII', data, sec + 8)
    if name == '.text':
        text_sec = (r_addr, r_size, v_addr)
        break

print('.text section:', text_sec)
r_addr, r_size, v_addr = text_sec

# Search for disp32
# An instruction like 48 8d 15 [disp32] (lea rdx, [rip+disp32]) has length 7
# disp32 = str_rva - (curr_rva + 7)
# Let's scan for lea rdx/rcx/r8 pointing to str_rva
found = []
for off in range(r_addr, r_addr + r_size - 7):
    b0, b1, b2 = data[off], data[off+1], data[off+2]
    # 48 8D (REX.W LEA)
    if b0 == 0x48 and b1 == 0x8D:
        disp = struct.unpack_from('<i', data, off + 3)[0]
        curr_rva = v_addr + (off - r_addr)
        if curr_rva + 7 + disp == str_rva:
            found.append((off, curr_rva))

print('Found direct LEA references:', found)
