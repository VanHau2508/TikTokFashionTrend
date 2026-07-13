"""
Fashion Item Taxonomy - Simplified & Optimized for YOLOv8
21 distinct classes - no confusion
"""

FASHION_TAXONOMY = {
    # ========== TOPS (ÁO) ==========
    "tops": {
        "shirt": {
            "id": 0,
            "name": "Shirt", #286
            "yolo_class": "shirt",
            "description": "Áo sơ mi, áo cổ",
            "variations": ["áo sơ mi nam", "áo sơ mi nữ", "áo sơ mi công sở"]
        },
        "t_shirt": {
            "id": 1,
            "name": "T-shirt", #302
            "yolo_class": "t_shirt",
            "variations": ["áo thun nam", "áo thun nữ", "áo thun unisex", "áo thun basic", "áo thun in hình"],
            "description": "Áo thun cơ bản, ngắn tay, thường có cổ tròn"
        },
        "polo_shirt": {
            "id": 2,
            "name": "Polo Shirt", #280
            "yolo_class": "polo_shirt",
            "description": "Áo polo có cổ, cúc ở ngực",
            "variations": ["polo nam", "polo nữ", "polo thể thao"]
        },
        "crop_top": {
            "id": 3,
            "name": "Crop Top", #250
            "yolo_class": "crop_top",
            "description": "Áo crop top ngắn, hiện đại",
            "variations": ["crop top ngắn", "crop top ôm"]
        }
    },
    
    # ========== OUTERWEAR (ÁO KHOÁC) ==========
    "outerwear": {
        "jacket": {
            "id": 4,
            "name": "Jacket", #328
            "yolo_class": "jacket",
            "description": "Áo khoác kiểu, bomber, denim",
            "variations": ["jacket da", "jacket bomber", "jacket jean"]
        },
        "hoodie": {
            "id": 5,
            "name": "Hoodie", #306
            "yolo_class": "hoodie",
            "description": "Áo khoác có mũ, thường có kéo khóa",
            "variations": ["hoodie nam", "hoodie nữ", "hoodie zip"]
        },
        "cardigan": {
            "id": 6,
            "name": "Cardigan", #245
            "yolo_class": "cardigan",
            "description": "Áo khoác có cúc cài phía trước",
            "variations": ["cardigan len", "cardigan mỏng", "cardigan dài"]
        },
        "blazer": {
            "id": 7,
            "name": "Blazer", #388
            "yolo_class": "blazer",
            "description": "Áo blazer chính thức, công sở",
            "variations": ["blazer công sở", "blazer nữ", "blazer nam"]
        }
    },
    
    # ========== BOTTOMS (QUẦN) ==========
    "bottoms": {
        "shorts": {
            "id": 8,
            "name": "Shorts", #388
            "yolo_class": "shorts",
            "description": "Quần ngắn, thích hợp mùa hè",
            "variations": ["quần short nam", "quần short nữ", "quần short jean"]
        },
        "jeans": {
            "id": 9,
            "name": "Jeans", #384
            "yolo_class": "jeans",
            "description": "Quần jean xanh, đen, rách",
            "variations": ["jeans xanh", "jeans đen", "jeans rách", "jeans skinny"]
        },
        "pants": {
            "id": 10,
            "name": "Pants", #404
            "yolo_class": "pants",
            "description": "Quần tây, quần công sở, chinos",
            "variations": ["quần tây nam", "quần tây nữ", "quần chinos"]
        },
        "skirt": {
            "id": 11,
            "name": "Skirt", #270
            "yolo_class": "skirt",
            "description": "Váy nữ, chữ A, mini, midi, dài",
            "variations": ["váy chữ A", "váy mini", "váy midi", "váy dài"]
        }
    },
    
    # ========== DRESSES (ĐẦM) ==========
    "dresses": {
        "dress": {
            "id": 12,
            "name": "Dress", #439
            "yolo_class": "dress",
            "description": "Đầm, váy liền thân",
            "variations": ["đầm suông", "đầm ôm", "đầm dạo phố", "đầm dạ hội"]
        }
    },
    
    # ========== FOOTWEAR (GIÀY) ==========
    "footwear": {
        "sneakers": {
            "id": 13,
            "name": "Sneakers", #405
            "yolo_class": "sneakers",
            "description": "Giày thể thao, canvas, lưới",
            "variations": ["sneaker trắng", "sneaker đen", "sneaker cao", "sneaker thấp"]
        },
        "formal_shoes": {
            "id": 14,
            "name": "Formal Shoes", #255
            "yolo_class": "formal_shoes",
            "description": "Giày tây, giày da, chính thức",
            "variations": ["giày tây", "giày công sở", "giày da"]
        },
        "sandals": {
            "id": 15,
            "name": "Slippers", #slippers 231
            "yolo_class": "slippers",
            "description": "Dép xỏ ngón, dép quai ngang, dép nước",
            "variations": ["dép xỏ ngón", "dép quai ngang", "dép nước"]
        },
    },
    
    # ========== ACCESSORIES (PHỤ KIỆN) ==========
    "accessories": {
        "bags": {
            "id": 16,
            "name": "Bags", #361
            "yolo_class": "bags",
            "description": "Túi xách, túi da, túi vải",
            "variations": ["túi xách", "túi da", "túi vải", "túi công sở"]
        },
        "backpack": {
            "id": 17,
            "name": "Backpack", #406
            "yolo_class": "backpack",
            "description": "Ba lô, thoải mái cho vai",
            "variations": ["ba lô du lịch", "ba lô học sinh", "ba lô thể thao"]
        },
        "watch": {
            "id": 18,
            "name": "Watch",
            "yolo_class": "watch", #280
            "description": "Đồng hồ, quý phái và tiện lợi",
            "variations": ["đồng hồ nam", "đồng hồ nữ", "đồng hồ thể thao"]
        },
        "cap": {
            "id": 19,
            "name": "Cap",
            "yolo_class": "cap", #267
            "description": "Mũ/nón lưỡi trai, mũ phớt",
            "variations": ["mũ lưỡi trai", "mũ len", "mũ phớt"]
        },
        "sunglasses": {
            "id": 20,
            "name": "Sunglasses", #404
            "yolo_class": "sunglasses",
            "description": "Kính mát, kính thời trang",
            "variations": ["kính mát", "kính thời trang", "kính đọc sách"]
        }
    }
}

def get_item_by_class_name(class_name):
    """Lấy toàn bộ dictionary thông tin món đồ bằng tên yolo_class"""
    name_clean = class_name.lower().strip()
    for cat_items in FASHION_TAXONOMY.values():
        for item in cat_items.values():
            if item['yolo_class'] == name_clean:
                return item
    return None

def get_category_by_class_name(class_name):
    """Lấy tên category (tops, bottoms,...) từ yolo_class"""
    name_clean = class_name.lower().strip()
    for category, items in FASHION_TAXONOMY.items():
        for item in items.values():
            if item['yolo_class'] == name_clean:
                return category
    return 'unknown'

def get_class_names_list():
    """Lấy danh sách 21 yolo_class để mapping với Model"""
    names = []
    for cat in FASHION_TAXONOMY.values():
        for item in cat.values():
            names.append(item['yolo_class'])
    return names