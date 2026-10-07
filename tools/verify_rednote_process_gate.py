import struct
import zipfile


def verify_process_gate(apk, expected_package):
    with zipfile.ZipFile(apk) as archive:
        dex = archive.read('classes17.dex')
    def u32(offset):
        return struct.unpack_from('<I', dex, offset)[0]
    def uleb(offset):
        value = shift = 0
        while True:
            byte = dex[offset]
            offset += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value, offset
            shift += 7
    def string(index):
        offset = u32(u32(60) + 4 * index)
        _, offset = uleb(offset)
        return dex[offset:dex.index(b'\0', offset)].decode('utf-8', errors='replace')
    def descriptor(index):
        return string(u32(u32(68) + 4 * index))
    def method(index):
        cls, proto, name = struct.unpack_from('<HHI', dex, u32(92) + 8 * index)
        return descriptor(cls), string(name)
    def field(index):
        cls, typ, name = struct.unpack_from('<HHI', dex, u32(84) + 8 * index)
        return descriptor(cls), string(name), descriptor(typ)
    class_data = None
    for index in range(u32(96)):
        offset = u32(100) + 32 * index
        if descriptor(u32(offset)) == 'Lddc/a;':
            class_data = u32(offset + 24)
            break
    assert class_data, 'ddc.a missing'
    sizes = []
    offset = class_data
    for _ in range(4):
        value, offset = uleb(offset)
        sizes.append(value)
    for _ in range(sizes[0] + sizes[1]):
        _, offset = uleb(offset)
        _, offset = uleb(offset)
    matched = []
    for count in sizes[2:]:
        method_index = 0
        for _ in range(count):
            delta, offset = uleb(offset)
            method_index += delta
            _, offset = uleb(offset)
            code, offset = uleb(offset)
            if method(method_index) != ('Lddc/a;', 'invoke'):
                continue
            assert code, 'invoke has no code'
            count = u32(code + 12)
            units = struct.unpack_from('<' + 'H' * count, dex, code + 16)
            for pos in range(len(units) - 6):
                if units[pos] != 0x0062 or field(units[pos+1]) != ('Lddc/b;', 'b', 'Ljava/lang/String;'):
                    continue
                if units[pos+2] == 0x011a:
                    literal = string(units[pos+3]); invoke_pos = pos+4
                elif units[pos+2] == 0x011b:
                    literal = string(units[pos+3] | units[pos+4] << 16); invoke_pos = pos+5
                else:
                    continue
                if units[invoke_pos] != 0x2071 or units[invoke_pos+2] != 0x0010:
                    continue
                if method(units[invoke_pos+1]) != ('Lkotlin/jvm/internal/Intrinsics;', 'areEqual'):
                    continue
                matched.append(literal)
    assert matched == [expected_package], matched
    return {'dex': 'classes17.dex', 'class': 'ddc.a', 'method': 'invoke',
            'processNameConstant': expected_package, 'exactPredicateCount': 1}
