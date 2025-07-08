from utils import *
from zstd import *
import os
from typing import List, Tuple
from dataclasses import dataclass

def u8_popcount(value: int) -> int:
    value = (value & 0xff) - ((value >> 1) & 0x55)
    value = ((value >> 2) & 0x33) + (value & 0x33)
    return (value + (value >> 4)) & 0x0f

@dataclass
class WorldInfo:
    cave_or_indoor_distance: int # distance to entrance from interior
    water_distance: int
    forest_density: int
    # ty to howzieky for pointing out the directional flags
    surface_flags: int # bit 0 = east, 1 = west, 2 = up, 3 = down, 4 = north, 5 = south, 6 = water, 7 = miasma
    cave_entrance_distance: int # distance to cave entrance but from outside of cave
    material: int # botttom 4 bits is the water material
    route_dist: int
    water_depth: int
    water_flow_rate: int
    tera_mat: int
    forest_type_flags: int # bottom 5 bits is forest type, 6 = wilted, 7 = snowy
    _0b: int # maybe padding
    cave_id: int

@dataclass
class Area:
    pos: Tuple[int, int, int]
    voxel_masks: List[List[int]]
    surface_info: List[int]
    surface_info2: List[int]
    world_info: List[WorldInfo]

class Context:
    def __init__(self, romfs_path: str, world_name: str, gamedata_flags: List[str]):
        self.dctx = ZstdDecompContext(os.path.join(romfs_path, "Pack/ZsDic.pack.zs"))
        if world_name == "" or world_name == "MainField":
            self.init_defaults() # MainField has no context file, values are hardcoded
        else:
            self.load_context(os.path.join(romfs_path, "VolumeStats", world_name, "context.vsts.zs"))
        self.world_name = world_name
        self.romfs_path = romfs_path
        self.gamedata_flags = gamedata_flags

    def init_defaults(self) -> None:
        self.unit_size = [500, 8000, 500]
        self.world_base = [-5000, -4000, -4000]
        self.grid_dimensions = [20, 1, 16]
        # while these values can be loaded from the context file, the game's search
        # algorithm will not work properly unless sidelength + 2 * margin == 256
        self.area_margin = [3, 3, 3]
        self.area_sidelength = 250

    def load_context(self, context_path: str) -> None:
        stream: ReadStream = ReadStream(self.dctx.decompress(context_path))
        magic: bytes = stream.read(4)
        assert magic == b"VSTS", f"Invalid file magic! {magic}"
        stream.read(4) # padding
        self.unit_size = [stream.read_s32(), stream.read_s32(), stream.read_s32()]
        stream.read(4) # padding
        self.world_base = [stream.read_s32(), stream.read_s32(), stream.read_s32()]
        stream.read(4) # padding
        self.grid_dimensions = [stream.read_s32(), stream.read_s32(), stream.read_s32()]
        stream.read(4) # padding
        self.area_margin = [stream.read_s32(), stream.read_s32(), stream.read_s32()]
        self.area_sidelength = stream.read_s32()
    
    def load_unit(self, unit_path: str) -> List[Area]:
        stream: ReadStream = ReadStream(self.dctx.decompress(unit_path))
        magic: bytes = stream.read(4)
        assert magic == b"VSTS", f"Invalid file magic! {magic}"
        area_count: int = stream.read_u8()
        is_single_scene: bool = stream.read_u8() != 0
        unk_06: int = stream.read_u8()
        version: int = stream.read_u8()
        assert version == 0xa, f"Invalid file version! {hex(version)}"
        num_area_x: int = int(self.unit_size[0] / self.area_sidelength)
        num_area_y: int = int(self.unit_size[1] / self.area_sidelength)
        num_area_z: int = int(self.unit_size[2] / self.area_sidelength)
        assert area_count == num_area_x * num_area_y * num_area_z, "Mismatching area count!"
        areas: List[Area] = []
        # areas are arranged in X -> Z -> Y order
        for y in range(num_area_y):
            for z in range(num_area_z):
                for x in range(num_area_x):
                    areas.append(self.load_area(stream, is_single_scene, x, y, z))
        return areas

    def load_area(self, stream: ReadStream, is_single_scene: bool, x: int, y: int, z: int) -> Area:
        size: int = stream.read_u32()
        pos: int = stream.tell()
        area: Area = Area((x, y, z), self.load_voxel_masks(stream), [], [], [])
        assert stream.tell() - pos == size, "Incorrect size!"
        size = stream.read_u32()
        area.surface_info.extend(struct.unpack(f"{size}B", stream.read(size)))
        if not is_single_scene:
            size = stream.read_u32()
            area.surface_info2.extend(struct.unpack(f"{size}B", stream.read(size)))
            for i in range(stream.read_u32()):
                area.world_info.append(WorldInfo(*struct.unpack("<12BQ", stream.read(0x14))))
        return area
    
    def load_voxel_masks(self, stream: ReadStream) -> List[List[int]]:
        masks: List[List[int]] = []
        for i in range(8):
            masks.append([])
            count: int = stream.read_u32()
            for j in range(count):
                masks[i].append(stream.read_u32())
        return masks
    
    def dump_unit_obj(self, unit_path: str, unit_base: List[int], outfile: io.FileIO) -> int:
        areas: List[Area] = self.load_unit(unit_path)

        positions: List[List[int]] = []

        for area in areas:
            base_pos: List[int] = [
                self.area_sidelength * area.pos[0] - self.area_margin[0] + unit_base[0],
                self.area_sidelength * area.pos[1] - self.area_margin[1] + unit_base[1],
                self.area_sidelength * area.pos[2] - self.area_margin[2] + unit_base[2]
            ]

            if len(area.voxel_masks[0]) > 0:
                self.iterate_octree(base_pos, positions, area, 0, 0)

        for pos in positions:
            outfile.write(f"v {pos[0]} {pos[1]} {pos[2]}\n")
            # outfile.write(f"v {pos[0] + 1} {pos[1]} {pos[2]}\n")
            # outfile.write(f"v {pos[0]} {pos[1]} {pos[2] + 1}\n")
            # outfile.write(f"v {pos[0] + 1} {pos[1]} {pos[2] + 1}\n")
            # outfile.write(f"v {pos[0]} {pos[1] + 1} {pos[2]}\n")
            # outfile.write(f"v {pos[0] + 1} {pos[1] + 1} {pos[2]}\n")
            # outfile.write(f"v {pos[0]} {pos[1] + 1} {pos[2] + 1}\n")
            # outfile.write(f"v {pos[0] + 1} {pos[1] + 1} {pos[2] + 1}\n")
        
        outfile.write("\n")

        return len(positions)
    
    @staticmethod
    def get_index(pos_flag: int, mask: int) -> int:
        return u8_popcount(mask & (-1 << pos_flag ^ 0xffffffff)) + (mask >> 8)

    def iterate_octree(self, base_pos: List[int], positions: List[List[int]], area: Area, mask_index: int, level: int = 0) -> None:
        mask: int = area.voxel_masks[level][mask_index]
        if level == 7:
            # iterate through child nodes (optionally filtered by surface info)
            for i in range(8):
                if mask >> i & 1 == 0:
                    continue
                # index: int = self.get_index(i, mask)
                # bit_offset: int = index * 10
                # flags: int = (area.surface_info[bit_offset >> 3] >> (bit_offset & 7)) & 0x3ff
                positions.append([
                    base_pos[0] + (i & 1) * (1 << (7 - level)),
                    base_pos[1] + (i >> 1 & 1) * (1 << (7 - level)),
                    base_pos[2] + (i >> 2 & 1) * (1 << (7 - level))
                ])
        else:
            if level == 6:
                # iterate through child nodes (optionally filtered by ???)
                for i in range(8):
                    if mask >> i & 1 == 0:
                        continue
                    index: int = self.get_index(i, mask)
                    # bit_offset: int = index * 6
                    # flags: int = (area.surface_info2[bit_offset >> 3] >> (bit_offset & 7)) & 0x3f
                    new_pos: List[int] = [
                        base_pos[0] + (i & 1) * (1 << (7 - level)),
                        base_pos[1] + (i >> 1 & 1) * (1 << (7 - level)),
                        base_pos[2] + (i >> 2 & 1) * (1 << (7 - level))
                    ]
                    self.iterate_octree(new_pos, positions, area, index, level + 1)
            elif level == 5:
                # iterate through child nodes (optionally filtered by world info)
                for i in range(8):
                    if mask >> i & 1 == 0:
                        continue
                    index: int = self.get_index(i, mask)
                    # info: WorldInfo = area.world_info[index]
                    new_pos: List[int] = [
                        base_pos[0] + (i & 1) * (1 << (7 - level)),
                        base_pos[1] + (i >> 1 & 1) * (1 << (7 - level)),
                        base_pos[2] + (i >> 2 & 1) * (1 << (7 - level))
                    ]
                    self.iterate_octree(new_pos, positions, area, index, level + 1)
            else:
                # iterate through child nodes
                for i in range(8):
                    if mask >> i & 1 == 0:
                        continue
                    index: int = self.get_index(i, mask)
                    new_pos: List[int] = [
                        base_pos[0] + (i & 1) * (1 << (7 - level)),
                        base_pos[1] + (i >> 1 & 1) * (1 << (7 - level)),
                        base_pos[2] + (i >> 2 & 1) * (1 << (7 - level))
                    ]
                    self.iterate_octree(new_pos, positions, area, index, level + 1)
    
    def dump_obj(self, outpath: str) -> None:
        with open(outpath, "w", encoding="utf-8") as outfile:
            total: int = 0
            for x in range(self.grid_dimensions[0]):
                for z in range(self.grid_dimensions[2]):
                    path: str = os.path.join(self.romfs_path, "VolumeStats", self.world_name, f"X{x}_Z{z}.vsts.zs")
                    # note MainField has some units that are swapped out depending on GameData flags
                    # the proper way to do this is to parse the vstats WorldParam file
                    if self.gamedata_flags:
                        for flag in self.gamedata_flags:
                            gmd_path = os.path.exists(os.path.join(self.romfs_path, "VolumeStats", self.world_name, flag, f"X{x}_Z{z}.vsts.zs"))
                            if os.path.exists(gmd_path):
                                path = gmd_path
                                break
                    print(path)
                    base_pos: List[int] = [
                        self.world_base[0] + self.unit_size[0] * x,
                        self.world_base[1],
                        self.world_base[2] + self.unit_size[2] * z
                    ]
                    total += self.dump_unit_obj(path, base_pos, outfile)
            # with such a naive approach, writing the faces for the voxels takes forever so don't bother
            # for i in range(total):
            #     outfile.write(f"f {i * 8 + 1} {i * 8 + 2} {i * 8 + 4} {i * 8 + 3}\n")
            #     outfile.write(f"f {i * 8 + 1} {i * 8 + 2} {i * 8 + 6} {i * 8 + 5}\n")
            #     outfile.write(f"f {i * 8 + 1} {i * 8 + 3} {i * 8 + 7} {i * 8 + 5}\n")
            #     outfile.write(f"f {i * 8 + 2} {i * 8 + 4} {i * 8 + 8} {i * 8 + 6}\n")
            #     outfile.write(f"f {i * 8 + 3} {i * 8 + 4} {i * 8 + 8} {i * 8 + 7}\n")
            #     outfile.write(f"f {i * 8 + 5} {i * 8 + 6} {i * 8 + 8} {i * 8 + 7}\n")

    def dump_individual_objs(self, outdir: str = "") -> None:
        if outdir:
            os.makedirs(outdir, exist_ok=True)
        for x in range(self.grid_dimensions[0]):
            for z in range(self.grid_dimensions[2]):
                path: str = os.path.join(self.romfs_path, "VolumeStats", self.world_name, f"X{x}_Z{z}.vsts.zs")
                # note MainField has some units that are swapped out depending on GameData flags
                # the proper way to do this is to parse the vstats WorldParam file
                if self.gamedata_flags:
                    for flag in self.gamedata_flags:
                        gmd_path = os.path.join(self.romfs_path, "VolumeStats", self.world_name, flag, f"X{x}_Z{z}.vsts.zs")
                        if os.path.exists(gmd_path):
                            path = gmd_path
                            break
                with open(os.path.join(outdir, f"{self.world_name}_X{x}_Z{z}.obj"), "w", encoding="utf-8") as outfile:
                    print(path)
                    base_pos: List[int] = [
                        self.world_base[0] + self.unit_size[0] * x,
                        self.world_base[1],
                        self.world_base[2] + self.unit_size[2] * z
                    ]
                    self.dump_unit_obj(path, base_pos, outfile)
    
    def dump_unit_obj_individual(self, x: int, z: int, outdir: str = "", gamedata: str = "") -> None:
        if outdir:
            os.makedirs(outdir, exist_ok=True)
        if gamedata == "":
            path: str = os.path.join(self.romfs_path, "VolumeStats", self.world_name, f"X{x}_Z{z}.vsts.zs")
        else:
            path: str = os.path.join(self.romfs_path, "VolumeStats", self.world_name, gamedata, f"X{x}_Z{z}.vsts.zs")
        with open(os.path.join(outdir, f"{self.world_name}_X{x}_Z{z}.obj"), "w", encoding="utf-8") as outfile:
            self.dump_unit_obj(path, [0, self.world_base[1], 0], outfile)

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        romfs_path: str = input("romfs path: ")
    else:
        romfs_path: str = sys.argv[1]
    
    if len(sys.argv) < 3:
        world_name: str = input("world name: ")
    else:
        world_name: str = sys.argv[2]
    
    if world_name == "MainField":
        flags: List[str] = ["SageOfGerudo_IsAfter_DungeonBossDead_Exp", "SageOfGerudo_IsAfter_DungeonFind_Exp", "SageOfSoul_HiddenStairsAppear"]
    else:
        flags: List[str] = []
    ctx: Context = Context(romfs_path, world_name, flags)
    # MainField takes around 10 min and produces a 9 gb obj file so...
    if world_name == "MainField":
        ctx.dump_individual_objs("MainFieldOut")
    else:
        ctx.dump_obj(f"{world_name}.obj")