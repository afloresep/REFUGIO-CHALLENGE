def create_layout() -> dict[str, object]:
    # Wide avenues: fewer, taller rack walls with broad north-south corridors.
    shelves: list[list[int]] = []
    for x0 in (4, 8, 13, 17, 22, 27, 32, 36, 41, 45):
        for x in (x0, x0 + 1):
            for y in range(2, 50):
                shelves.append([x, y])
    return {"schema_version": 1, "shelves": shelves}
