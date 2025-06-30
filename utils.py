import struct
import io

def get_string(data, offset):
    if type(data) != bytes:
        data = data.read()
    end = data.find(b'\x00', offset)
    return data[offset:end].decode('utf-8')

class Stream:
    __slots__ = ["stream"]

    def __init__(self, stream) -> None:
        self.stream = stream

    def seek(self, *args) -> None:
        self.stream.seek(*args)

    def tell(self) -> int:
        return self.stream.tell()

    def skip(self, skip_size) -> None:
        self.stream.seek(skip_size, 1)

class ReadStream(Stream):
    def __init__(self, data) -> None:
        stream = io.BytesIO(memoryview(data))
        super().__init__(stream)
        self.data = data

    def read(self, *args) -> bytes:
        return self.stream.read(*args)
    
    def read_u8(self, end="<") -> int:
        return struct.unpack(f"{end}B", self.read(1))[0]
    
    def read_u16(self, end="<") -> int:
        return struct.unpack(f"{end}H", self.read(2))[0]
    
    def read_s16(self, end="<") -> int:
        return struct.unpack(f"{end}h", self.read(2))[0]
    
    def read_u24(self, end="<") -> int:
        if end == "<":
            return struct.unpack(f"{end}I", self.read(3) + b'\x00')[0]
        else:
            return struct.unpack(f"{end}I", b'\x00' + self.read(3))[0]
        
    def read_s24(self, end="<") -> int:
        if end == "<":
            return struct.unpack(f"{end}i", self.read(3) + b'\x00')[0]
        else:
            return struct.unpack(f"{end}i", b'\x00' + self.read(3))[0]
    
    def read_u32(self, end="<") -> int:
        return struct.unpack(f"{end}I", self.read(4))[0]
    
    def read_s32(self, end="<") -> int:
        return struct.unpack(f"{end}i", self.read(4))[0]
    
    def read_u64(self, end="<") -> int:
        return struct.unpack(f"{end}Q", self.read(8))[0]
    
    def read_s64(self, end="<") -> int:
        return struct.unpack(f"{end}q", self.read(8))[0]
    
    def read_ptr(self, align=8, end="<") -> int:
        while self.stream.tell() % align != 0:
            self.read(1)
        return struct.unpack(f"{end}Q", self.read(8))[0]
    
    def read_f32(self, end="<") -> float:
        return struct.unpack(f"{end}f", self.read(4))[0]
    
    def read_f64(self, end="<") -> float:
        return struct.unpack(f"{end}d", self.read(4))[0]

    def read_string(self, offset=None, size=4): # Data should be a slice beginning at the string pool
        pos = self.stream.tell()
        if offset == None:
            if size == 4:
                ptr = self.read_u32()
            elif size == 2:
                ptr = self.read_u16()
            elif size == 8:
                ptr = self.read_u64()
            else:
                raise Exception("Please provide relative offset for other data sizes")
        else:
            ptr = offset
        string = get_string(self.stream, ptr)
        self.stream.seek(pos)
        return string