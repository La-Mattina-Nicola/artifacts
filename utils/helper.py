def resolve_to_node_code(world_map, resource_code: str, items_db=None):
    # ✅ déjà un node de map
    if resource_code in world_map.resources:
        return resource_code

    # ✅ via items_db
    if items_db:
        item = items_db.get_by_code(resource_code)
        if item:
            subtype = getattr(item, "subtype", None)

            suffix_map = {
                "alchemy": "_field",
                "mining": "_rock",
                "woodcutting": "_tree",
                "fishing": "_spot",
            }

            suffix = suffix_map.get(subtype)
            if suffix:
                candidate = resource_code + suffix
                if candidate in world_map.resources:
                    return candidate

    # 🧪 fallback
    for suffix in ["_field", "_rock", "_tree", "_spot"]:
        candidate = resource_code + suffix
        if candidate in world_map.resources:
            return candidate

    return None
