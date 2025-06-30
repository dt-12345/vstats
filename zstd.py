try:
    import zstandard as zstd
except ImportError:
    raise ImportError("zstandard not found (pip install zstandard)")
try:
    import oead # pyright: ignore[reportMissingImports]
except ImportError:
    print("oead not found (pip install oead)")
    print("using sarc.py instead")
    try:
        import sarc
    except ImportError:
        raise ImportError("sarc.py not found")
from functools import lru_cache
from pathlib import Path
from typing import Dict
import enum
import sys

class DictType(enum.Enum):
    ZSDIC = 1
    BCETT = 2
    PACK  = 3

class ZstdDecompressor(zstd.ZstdDecompressor):
    def __init__(self, dictionary: zstd.ZstdCompressionDict=None, format: int=zstd.FORMAT_ZSTD1) -> None:
        super().__init__(dict_data=dictionary, format=format)

    def _decompress(self, data: bytes) -> bytes:
        return self.decompress(data)
    
class ZstdCompressor(zstd.ZstdCompressor):
    def __init__(self, dictionary: zstd.ZstdCompressionDict=None) -> None:
        super().__init__(dict_data=dictionary)
    
    def _compress(self, data: bytes) -> bytes:
        return self.compress(data)

class ZstdDecompContext:
    @lru_cache
    def __init__(self, zsdic_pack_path: str="") -> None:
        vanilla_decompressor: zstd.ZstdDecompressor = zstd.ZstdDecompressor()
        if "oead" in sys.modules:
            archive: oead.Sarc = oead.Sarc(vanilla_decompressor.decompress(Path(zsdic_pack_path).read_bytes()))
            dictionaries: Dict[str, zstd.ZstdCompressionDict] = {f.name: zstd.ZstdCompressionDict(f.data) for f in archive.get_files()}
        else:
            archive: sarc.Sarc = sarc.Sarc(vanilla_decompressor.decompress(Path(zsdic_pack_path).read_bytes()))
            dictionaries: Dict[str, zstd.ZstdCompressionDict] = {i["Name"] : zstd.ZstdCompressionDict(i["Data"]) for i in archive.files}
        self.pack: ZstdDecompressor = ZstdDecompressor(dictionaries["pack.zsdic"])
        self.bcett: ZstdDecompressor = ZstdDecompressor(dictionaries["bcett.byml.zsdic"])
        self.zs: ZstdDecompressor = ZstdDecompressor(dictionaries["zs.zsdic"])
        self.mc: ZstdDecompressor = ZstdDecompressor(format=zstd.FORMAT_ZSTD1_MAGICLESS)
        self.pack_compress: ZstdCompressor = ZstdCompressor(dictionaries["pack.zsdic"])
        self.bcett_compress: ZstdCompressor = ZstdCompressor(dictionaries["bcett.byml.zsdic"])
        self.zs_compress: ZstdCompressor = ZstdCompressor(dictionaries["zs.zsdic"])
    
    def decompress(self, filepath: str) -> bytes:
        if not(filepath.endswith(".zs") or filepath.endswith(".zstd") or filepath.endswith(".mc")):
            return Path(filepath).read_bytes()
        elif filepath.endswith(".mc"):
            return self.mc._decompress(Path(filepath).read_bytes()[0xc:])
        data: bytes = Path(filepath).read_bytes()
        id: int = zstd.get_frame_parameters(data).dict_id
        if id == 1:
            return self.zs._decompress(data)
        elif id == 2:
            return self.bcett._decompress(data)
        elif id == 3:
            return self.pack._decompress(data)
        else:
            return self.zs._decompress(data)
    
    def compress(self, filepath: str, dict: DictType = DictType.ZSDIC) -> bytes:
        if dict == DictType.PACK:
            return self.pack_compress._compress(Path(filepath).read_bytes())
        elif dict == DictType.BCETT:
            return self.bcett_compress._compress(Path(filepath).read_bytes())
        else:
            return self.zs_compress._compress(Path(filepath).read_bytes())