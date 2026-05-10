def resolve_to_node_code(world_map, resource_code: str, items_db=None):
    if resource_code in world_map.resources:
        return resource_code

    if items_db:
        item = items_db.get_by_code(resource_code)
        if item:
            subtype = getattr(item, "subtype", None)

            suffix_map = {
                "alchemy": ("", "_field"),
                "mining": ("_ore|_stone", "_rocks"),
                "woodcutting": ("_log|_wood", "_tree"),
                "fishing": ("", "_spot"),
            }

            if subtype in suffix_map:
                strip_pattern, add_suffix = suffix_map[subtype]
                base = resource_code
                for strip in strip_pattern.split("|"):
                    if strip and base.endswith(strip):
                        base = base[: -len(strip)]
                        break
                candidate = base + add_suffix
                if candidate in world_map.resources:
                    return candidate

    for suffix in ["_rocks", "_field", "_tree", "_spot"]:
        candidate = resource_code + suffix
        if candidate in world_map.resources:
            return candidate
        for strip in ["_ore", "_stone", "_log"]:
            if resource_code.endswith(strip):
                candidate = resource_code[: -len(strip)] + suffix
                if candidate in world_map.resources:
                    return candidate

    return None
