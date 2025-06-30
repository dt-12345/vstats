#pragma pattern_limit 0x1000000

#include <std/sys.pat>

struct ResArray<T> {
    u32 size;
    T data[size];
};

struct ResWorldInfo {
    u8 cave_or_indoor_distance;
    u8 water_distance;
    u8 forest_density;
    u8 surface_flags; // bit 6 = water, bit 7 = miasma
    u8 _04; // some other cave-related distance
    u8 material; // botttom 4 bits is the water material
    u8 route_dist;
    u8 water_depth;
    u8 water_flow_rate;
    u8 tera_mat;
    u8 forest_type_flags; // bottom 5 bits is forest type, 6 = wilted, 7 = snowy
    u8 _0b;
    u64 cave_id;
};

struct ResArea<auto is_single_scene> {
    ResArray<u8> node_data;
    
    /*
        each area is divided into voxels (area size is set in the context file
        or hardcoded in the case of MainField)
        the root level voxel covers the entire area
        each voxel is then subdivided into eight children forming an octree
        this tree has 8 lod levels total and these define the mask of what
        children are present 
    */
    ResArray<u32> child_masks[8] @ addressof(node_data.data);
    std::assert(sizeof(child_masks) == node_data.size, "file error");
    
    /*
        10 bits per entry
        0 = ?
        1 = ?
        2 = ceiling
        3 = floor
        4 = ?
        5 = ?
        6 = indoors
        7 = cave
        8 = valid traveler checkpoint (?)
        9 = ?
    */
    ResArray<u8> surface_info; // for each 1x1x1 voxel
    
    if (!is_single_scene) {
        /*
            6 bits per entry
            ???
        */
        ResArray<u8> unk2; // for each 2x2x2 voxel
        ResArray<ResWorldInfo> world_info; // for each 4x4x4 voxel
    }
};

struct ResUnit {
    char magic[4];
    std::assert(magic == "VSTS", "file error");
    u8 area_count;
    bool is_single_scene;
    u8 _06;
    u8 version; // ?, needs to be 0xa
    std::assert(version == 0xa, "file error");
    
    ResArea<is_single_scene> areas[area_count];
};

ResUnit file @ 0x00;