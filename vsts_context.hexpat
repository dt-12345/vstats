struct Vector3i {
    s32 x, y, z;
};

struct ResContext {
    u32 magic; // VSTS
    u32 _04;
    Vector3i unit_size;
    u32 _14;
    Vector3i world_base_pos;
    u32 _24;
    Vector3i unit_grid_dimensions;
    u32 _34;
    Vector3i voxel_tree_margin; // overlapping margin area
    s32 voxel_tree_side_length;
};

ResContext file @ 0x00;