import struct, zipfile

def verify_fold_gates(apk):
    with zipfile.ZipFile(apk) as z:
        dex = z.read('classes4.dex')
    def u32(offset): return struct.unpack_from('<I', dex, offset)[0]
    def uleb(offset):
        value=shift=0
        while True:
            byte=dex[offset]; offset+=1
            value|=(byte&127)<<shift
            if byte<128: return value,offset
            shift+=7
    def string(index):
        offset=u32(u32(60)+4*index)
        _,offset=uleb(offset)
        return dex[offset:dex.index(b'\0',offset)].decode('utf-8')
    def descriptor(index): return string(u32(u32(68)+4*index))
    target='Lcom/xingin/adaptation/device/DeviceInfoContainer;'
    class_data=None
    for index in range(u32(96)):
        offset=u32(100)+32*index
        if descriptor(u32(offset))==target:
            class_data=u32(offset+24); break
    assert class_data, 'Target class not found'
    sizes=[]; offset=class_data
    for _ in range(4):
        value,offset=uleb(offset); sizes.append(value)
    for _ in range(sizes[0]+sizes[1]):
        _,offset=uleb(offset); _,offset=uleb(offset)
    found={}
    for count in sizes[2:]:
        method_index=0
        for _ in range(count):
            delta,offset=uleb(offset); method_index+=delta
            _,offset=uleb(offset); code,offset=uleb(offset)
            method_name=string(u32(u32(92)+8*method_index+4))
            if method_name in {'isHorizontalFolderDevice','isPad'}:
                assert code, method_name+' has no code'
                count=u32(code+12)
                instructions=list(struct.unpack_from('<'+'H'*count,dex,code+16))
                assert instructions==[0x1012,0x000f], (method_name,instructions)
                found[method_name]={'dex':'classes4.dex','instructions':['const/4 v0, 1','return v0'],'returnsTrue':True}
    assert len(found)==2, found
    return found
