# ── db.py — SQLite connection & helpers ───────────────────────────────────────
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

# SQLite DB file lives next to this file
DB_PATH = os.path.join(os.path.dirname(__file__), 'threadverse.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Generic helpers ───────────────────────────────────────────────────────────

def query(sql, args=None):
    """Run SELECT, return list of dicts."""
    conn = get_conn()
    try:
        cur = conn.execute(sql, args or ())
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def query_one(sql, args=None):
    """Run SELECT, return first row as dict or None."""
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql, args=None):
    """Run INSERT/UPDATE/DELETE, return lastrowid."""
    conn = get_conn()
    try:
        cur = conn.execute(sql, args or ())
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ── Schema bootstrap — runs once on first start ───────────────────────────────

def init_db():
    """Create all tables and seed data if the DB doesn't exist yet."""
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
    PRAGMA journal_mode=WAL;
    PRAGMA foreign_keys=ON;

    CREATE TABLE IF NOT EXISTS users (
        id               TEXT PRIMARY KEY,
        name             TEXT NOT NULL,
        email            TEXT NOT NULL UNIQUE,
        password         TEXT NOT NULL,
        role             TEXT NOT NULL DEFAULT 'customer',
        shop_name        TEXT,
        created          TEXT,
        contact_number   TEXT,
        verification_doc TEXT,
        google_id        TEXT,
        is_verified      INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS products (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        category    TEXT NOT NULL,
        subcategory TEXT,
        gender      TEXT DEFAULT 'unisex',
        color       TEXT,
        sizes       TEXT,
        price       REAL NOT NULL,
        occasion    TEXT,
        tags        TEXT,
        rating      REAL DEFAULT 0,
        reviews     INTEGER DEFAULT 0,
        stock       INTEGER DEFAULT 0,
        image       TEXT,
        description TEXT,
        vendor_id   TEXT REFERENCES users(id),
        vendor_name TEXT
    );

    CREATE TABLE IF NOT EXISTS orders (
        id               TEXT PRIMARY KEY,
        user_id          TEXT REFERENCES users(id),
        total            REAL NOT NULL DEFAULT 0,
        status           TEXT DEFAULT 'Confirmed',
        date             TEXT,
        shipping_name    TEXT,
        shipping_address TEXT,
        shipping_city    TEXT
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id      TEXT REFERENCES orders(id) ON DELETE CASCADE,
        product_id    INTEGER REFERENCES products(id),
        name          TEXT,
        price         REAL,
        qty           INTEGER DEFAULT 1,
        selected_size TEXT,
        image         TEXT
    );

    CREATE TABLE IF NOT EXISTS cart (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id    TEXT NOT NULL,
        product_id    INTEGER REFERENCES products(id),
        name          TEXT,
        price         REAL,
        qty           INTEGER DEFAULT 1,
        selected_size TEXT,
        image         TEXT
    );

    CREATE TABLE IF NOT EXISTS wishlist (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  TEXT NOT NULL,
        product_id  INTEGER REFERENCES products(id),
        name        TEXT,
        price       REAL,
        image       TEXT
    );
    """)

    # ── Seed users (only if table is empty) ──────────────────────────────────
    if not cur.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        from werkzeug.security import generate_password_hash as gph
        cur.execute("""INSERT OR IGNORE INTO users
            (id,name,email,password,role,shop_name,created) VALUES
            ('u001','Demo Customer','customer@demo.com',?,'customer',NULL,'01 Jan 2026')""",
            (gph('demo123'),))
        cur.execute("""INSERT OR IGNORE INTO users
            (id,name,email,password,role,shop_name,created) VALUES
            ('v001','Style House','vendor@demo.com',?,'vendor','Style House','01 Jan 2026')""",
            (gph('demo123'),))

    # ── Seed products (only if table is empty) ────────────────────────────────
    if not cur.execute("SELECT 1 FROM products LIMIT 1").fetchone():
        products = [
            (1,'Classic White Oxford Shirt','shirts','formal','men','white','S,M,L,XL,XXL',1499.0,'office','office,formal,classic',4.5,210,20,'https://plus.unsplash.com/premium_photo-1678218594563-9fe0d16c6838?w=600&auto=format&fit=crop&q=60','','v001','ThreadVerse'),
            (2,'Sky Blue Formal Shirt','shirts','formal','men','sky blue','S,M,L,XL,XXL',1599.0,'office','office,formal,smart',4.4,185,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTnuBOc7rLIkYMtsuosETArYVT2AG1tq2MmGA&s','','v001','ThreadVerse'),
            (3,'Black Party Shirt','shirts','party','men','black','S,M,L,XL,XXL',1799.0,'party','party,night out,slim fit',4.6,160,20,'https://rukminim2.flixcart.com/image/480/640/xif0q/shirt/1/v/i/xl-party-wear-satin-shirt-for-men-solstice-original-imah4xbfczxhgzrz.jpeg?q=90','','v001','ThreadVerse'),
            (4,'Navy Striped Shirt','shirts','formal','men','navy','S,M,L,XL,XXL',1399.0,'office','office,stripes,smart',4.3,142,20,'https://www.iconicindia.com/cdn/shop/files/GMS24-3240031409_2_6399a530-2ca1-47d8-97ff-fdab743065ee.jpg?v=1754665010&width=1445','','v001','ThreadVerse'),
            (5,'Burgundy Satin Party Shirt','shirts','party','men','burgundy','S,M,L,XL,XXL',1999.0,'party','party,satin,festive',4.7,130,20,'https://5.imimg.com/data5/ECOM/Default/2024/5/418709575/TG/BP/KI/56386717/1705639278-635305630-500x500.jpg','','v001','ThreadVerse'),
            (6,'Olive Casual Linen Shirt','shirts','casual','men','olive','S,M,L,XL,XXL',1299.0,'casual','casual,linen,summer',4.2,118,20,'https://encrypted-tbn3.gstatic.com/shopping?q=tbn:ANd9GcSz1I1XxFFQpuxeMaJH44tZQMiT-R_k8A-k-Fiym3g_IjCYtlcTy6yrBweRx6AFwzBzXDCOtolfLppE-AzaepCl2Kvh257EzicrbZ2qHQz0FfoD_h6rHRcI6bMoEYNk-ZM2Lc58YMJqBDgQs4vxAQ&usqp=CAc','','v001','ThreadVerse'),
            (7,'White Casual Oversized Shirt','shirts','casual','men','white','S,M,L,XL,XXL',1199.0,'casual','casual,oversized,everyday',4.1,95,20,'https://encrypted-tbn1.gstatic.com/shopping?q=tbn:ANd9GcQ3wfXCCwUj2vXt2qNG56T93VWHmAhs8O1tUmhTwL0dYT48YIi-h3NYhUyyZfzpyrW5Id11_Am3f_z5MfEzr0TfuYclj0ZPAbM9GZOYKAO6Zsd8kG7o9YxQ-1-0b8rpQp-XXKk_w7b_OZph&usqp=CAc','','v001','ThreadVerse'),
            (8,'Grey Checked Casual Shirt','shirts','casual','men','grey','S,M,L,XL,XXL',1349.0,'casual','casual,checked,relaxed',4.3,108,20,'https://www.menincrown.in/cdn/shop/files/666_37792448-4750-446f-87d2-bc0fa9508acd.jpg?v=1724749468','','v001','ThreadVerse'),
            (9,'Royal Blue Slim Fit Shirt','shirts','formal','men','royal blue','S,M,L,XL,XXL',1699.0,'office','office,slim fit,formal',4.5,175,20,'https://frayline.com/cdn/shop/files/variant-image-_-05-5_jpeg.jpg?v=1704174210','','v001','ThreadVerse'),
            (10,'Peach Floral Casual Shirt','shirts','casual','men','peach','S,M,L,XL,XXL',1249.0,'casual','casual,floral,summer',4.0,88,20,'https://m.media-amazon.com/images/I/81huvPN+dKL._AC_UY1100_.jpg','','v001','ThreadVerse'),
            (11,'Red Bodycon Party Dress','dresses','party','women','red','S,M,L,XL,XXL',2499.0,'party','party,bodycon,night out',4.7,230,20,'https://i.pinimg.com/474x/35/ca/a0/35caa0a40b121044732297baf9337218.jpg','','v001','ThreadVerse'),
            (12,'Black Sequin Party Dress','dresses','party','women','black','S,M,L,XL,XXL',3199.0,'party','party,sequin,festive',4.8,215,20,'https://i.ebayimg.com/images/g/g00AAOSwrSVip4z0/s-l400.jpg','','v001','ThreadVerse'),
            (13,'Cobalt Blue Wrap Party Dress','dresses','party','women','cobalt blue','S,M,L,XL,XXL',2299.0,'party','party,wrap,elegant',4.6,198,20,'https://cdn.fynd.com/v2/falling-surf-7c8bb8/fyprod/wrkr/products/pictures/item/free/original/T1iJRzIPZ-product.jpeg','','v001','ThreadVerse'),
            (14,'Pink Floral Maxi Dress','dresses','floral','women','pink','S,M,L,XL,XXL',1999.0,'casual','floral,casual,summer,maxi',4.5,172,20,'https://i.ebayimg.com/images/g/pwQAAOSwfcNdwmVo/s-l500.jpg','','v001','ThreadVerse'),
            (15,'Yellow Floral Sundress','dresses','floral','women','yellow','S,M,L,XL,XXL',1799.0,'casual','floral,summer,casual,breezy',4.4,155,20,'https://www.berrylush.com/cdn/shop/files/1_254bfd42-3efd-43fc-bd9a-6dd01658fbe8.jpg?v=1764413914&width=1920','','v001','ThreadVerse'),
            (16,'Green Floral Wrap Dress','dresses','floral','women','green','S,M,L,XL,XXL',2099.0,'casual','floral,wrap,casual,boho',4.5,163,20,'https://xcdn.next.co.uk/common/items/default/default/itemimages/3_4Ratio/product/lge/B70179s.jpg?im=Resize,width=750','','v001','ThreadVerse'),
            (17,'White Casual Shirt Dress','dresses','casual','women','white','S,M,L,XL,XXL',1699.0,'casual','casual,shirt dress,everyday',4.2,112,20,'https://www.urbansuburban.in/image/catalog/2024/cool-summer-24/dresses/S24-DRS-35-WX/4.jpg','','v001','ThreadVerse'),
            (18,'Lavender Casual Midi Dress','dresses','casual','women','lavender','S,M,L,XL,XXL',1899.0,'casual','casual,midi,relaxed',4.3,134,20,'https://globusfashion.com/media/catalog/product/cache/eff2e10f32e2f4a03e7bc00b9ed76e7e/w/c/wcgbecomkdrs5205-lavender-6.jpg','','v001','ThreadVerse'),
            (19,'Dusty Rose Casual Slip Dress','dresses','casual','women','dusty rose','S,M,L,XL,XXL',1599.0,'casual','casual,slip,minimal',4.1,98,20,'https://i.pinimg.com/474x/43/45/78/43457836129588d61ec338624e3f65e1.jpg','','v001','ThreadVerse'),
            (20,'Navy Floral Tea Dress','dresses','floral','women','navy','S,M,L,XL,XXL',2199.0,'casual','floral,tea dress,classic',4.6,187,20,'https://xcdn.next.co.uk/common/items/default/default/itemimages/3_4Ratio/product/lge/Y15136s.jpg?im=Resize,width=750','','v001','ThreadVerse'),
            (21,'Charcoal Slim Fit Trousers','pants','formal','men','charcoal','28,30,32,34,36',1999.0,'office','office,formal,slim fit',4.5,188,20,'https://pantproject.com/cdn/shop/files/1_84ee1258-fe3f-4010-b6b5-20db33b5f07b.jpg?v=1746820435&width=1080','','v001','ThreadVerse'),
            (22,'Navy Formal Chinos','pants','formal','men','navy','28,30,32,34,36',1799.0,'office','office,chinos,smart',4.4,165,20,'https://www.nicobar.com/cdn/shop/files/NBI038397_1_1200x.jpg?v=1738834111','','v001','ThreadVerse'),
            (23,'Beige Chinos','pants','casual','men','beige','28,30,32,34,36',1699.0,'casual','casual,chinos,versatile',4.3,142,20,'https://levi.in/cdn/shop/files/001K90004_04_Side.jpg?v=1740983143&width=1445','','v001','ThreadVerse'),
            (24,'Black Slim Fit Jeans','jeans','casual','men','black','28,30,32,34,36',2099.0,'casual','casual,slim fit,denim',4.6,210,20,'https://5.imimg.com/data5/LS/IO/EM/SELLER-86680741/mens-denim-black-faded-jeans-500x500.jpg','','v001','ThreadVerse'),
            (25,'Dark Indigo Straight Jeans','jeans','casual','men','dark indigo','28,30,32,34,36',1999.0,'casual','casual,straight fit,denim',4.5,196,20,'https://offduty.in/cdn/shop/files/Manfinity_RivetRise_Jeans_dcontrasts__jambe_effile_et_dlavs_pour_hommes__Mode_en_ligne__SHEIN_FRANCE_main_0.jpg?v=1755148348','','v001','ThreadVerse'),
            (26,'Grey Jogger Trousers','pants','casual','men','grey','28,30,32,34,36',1499.0,'casual','casual,jogger,relaxed',4.2,108,20,'https://muselot.in/cdn/shop/products/Unisex-plain-joggers-in-Melange-Grey-color-Muselot_2048x.jpg?v=1637447776','','v001','ThreadVerse'),
            (27,'Black Party Trousers','pants','party','men','black','28,30,32,34,36',2299.0,'party','party,night out,tapered',4.7,145,20,'https://bananaclub.co.in/cdn/shop/files/BlackLooseFitTrouser_3.jpg?v=1738820069','','v001','ThreadVerse'),
            (28,'Olive Cargo Trousers','pants','casual','men','olive','28,30,32,34,36',1899.0,'casual','casual,cargo,utility',4.3,122,20,'https://pantproject.com/cdn/shop/products/multi-pocket-pants.jpg?v=1667389898&width=720','','v001','ThreadVerse'),
            (29,'Khaki Smart Casual Chinos','pants','casual','men','khaki','28,30,32,34,36',1749.0,'casual','casual,smart,chinos',4.4,138,20,'https://assets.myntassets.com/dpr_1.5,q_30,w_400,c_limit,fl_progressive/assets/images/2025/NOVEMBER/24/xVb2l6wo_e061861290a943d3a6dfe71329f40591.jpg','','v001','ThreadVerse'),
            (30,'White Linen Trousers','pants','party','men','white','28,30,32,34,36',1999.0,'party','party,linen,summer formal',4.5,118,20,'https://uathayam.in/cdn/shop/files/88A7564.jpg?v=1757307258','','v001','ThreadVerse'),
            (31,'Black Formal Straight Trousers','pants','formal','women','black','S,M,L,XL,XXL',1999.0,'office','office,formal,straight leg',4.6,195,20,'https://imagescdn.allensolly.com/img/app/product/4/40084223-22087157.jpg','','v001','ThreadVerse'),
            (32,'Navy Wide Leg Trousers','pants','formal','women','navy','S,M,L,XL,XXL',2199.0,'office','office,wide leg,elegant',4.5,178,20,'https://encrypted-tbn2.gstatic.com/shopping?q=tbn:ANd9GcQJykwsBws4N9j3jCXWlKhKqnFi_-bSLIj68jfsWK-vgDyhjjZqJcDIi6EZH0Iz1t1VZnR8i6FqZ05pL9rG5GfY1iy3EU3Xw8kC5LHItMXr6EHuJ0aSsAwBw0VDc5BfBcVVaqQQBkU&usqp=CAc','','v001','ThreadVerse'),
            (33,'Cream High Waist Trousers','pants','formal','women','cream','S,M,L,XL,XXL',1899.0,'office','office,high waist,smart',4.4,162,20,'https://cdn.platform.next/common/items/default/default/itemimages/3_4Ratio/product/lge/B67619s3.jpg?im=Resize,width=180','','v001','ThreadVerse'),
            (34,'Camel Tailored Trousers','pants','formal','women','camel','S,M,L,XL,XXL',2099.0,'office','office,tailored,classic',4.5,155,20,'https://media3.newlookassets.com/i/newlook/865092517/womens/clothing/trousers/tall-camel-tailored-wide-leg-trousers.jpg?strip=true&qlt=50&w=720','','v001','ThreadVerse'),
            (35,'Dark Indigo Skinny Jeans','jeans','casual','women','dark indigo','S,M,L,XL,XXL',1799.0,'casual','casual,skinny,denim',4.4,185,20,'https://cdn.platform.next/common/items/default/default/itemimages/3_4Ratio/product/lge/K51061s.jpg','','v001','ThreadVerse'),
            (36,'White Straight Leg Jeans','jeans','casual','women','white','S,M,L,XL,XXL',1699.0,'casual','casual,straight,denim',4.3,140,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTO3DuEOKBd3YV8vzvfERa9nayKw0fydohPMA&s','','v001','ThreadVerse'),
            (37,'Burgundy Party Wide Leg Pants','pants','party','women','burgundy','S,M,L,XL,XXL',2299.0,'party','party,wide leg,festive',4.7,132,20,'https://xcdn.next.co.uk/common/items/default/default/itemimages/3_4Ratio/product/lge/AD8120s.jpg?im=Resize,width=750','','v001','ThreadVerse'),
            (38,'Sage Green Casual Trousers','pants','casual','women','sage green','S,M,L,XL,XXL',1599.0,'casual','casual,relaxed,everyday',4.2,112,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQQ1vmWwmjqV2BG7li8pc6yEiGD48QxUhFkGw&s','','v001','ThreadVerse'),
            (39,'Black Leather Look Trousers','pants','party','women','black','S,M,L,XL,XXL',2599.0,'party','party,leather,night out',4.8,148,20,'https://media2.newlookassets.com/i/newlook/905878001/womens/clothing/trousers/black-faux-leather-wide-leg-tailored-trousers.jpg?strip=true&qlt=50&w=720','','v001','ThreadVerse'),
            (40,'Olive Linen Trousers','pants','casual','women','olive','S,M,L,XL,XXL',1749.0,'casual','casual,linen,summer',4.3,108,20,'https://saadaa.in/cdn/shop/files/6_3285a5d8-977a-45b9-9bf6-38627db5e702.jpg?v=1754109961&width=1350','','v001','ThreadVerse'),
            (41,'White Basic Crew Neck Tee','tops','casual','unisex','white','S,M,L,XL,XXL',699.0,'casual','casual,basic,everyday',4.3,320,20,'https://encrypted-tbn1.gstatic.com/shopping?q=tbn:ANd9GcQpuNG-JIOVzOv72XUg-UrxtIQqsCRSIslDnaGuv4ZxryN4bpju_vHbsC2cSR2qBRc7Z1gl9al33V4DJC1shmPReNYt3dvCCHNxfEqWorb5ROo1CeiZBJRhKZ-oLATENsP-H_2CLXM&usqp=CAc','','v001','ThreadVerse'),
            (42,'Black Graphic Tee','tops','casual','unisex','black','S,M,L,XL,XXL',799.0,'casual','casual,graphic,streetwear',4.4,285,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS9G-8lw2utOHIuWpwFfwHbvRmGTmgnX1R8sQ&s','','v001','ThreadVerse'),
            (43,'Navy Essential Tee','tops','casual','unisex','navy','S,M,L,XL,XXL',749.0,'casual','casual,essential,minimal',4.2,260,20,'https://xcdn.next.co.uk/common/items/default/default/itemimages/3_4Ratio/product/lge/122159s4.jpg?im=Resize,width=750','','v001','ThreadVerse'),
            (44,'Grey Melange Tee','tops','casual','unisex','grey','S,M,L,XL,XXL',699.0,'casual','casual,melange,relaxed',4.3,240,20,'https://cdn11.bigcommerce.com/s-ey89nahkwo/images/stencil/original/products/1259/5280/UNISEX_REGULAR-FIT_LOGO_TEE_GREY_MELANGE_F1__47423.1747292152.jpg?c=1','','v001','ThreadVerse'),
            (45,'Olive Washed Tee','tops','casual','unisex','olive','S,M,L,XL,XXL',849.0,'casual','casual,washed,vintage',4.5,195,20,'https://stalworth.in/cdn/shop/files/7.png?v=1746476414','','v001','ThreadVerse'),
            (46,'Red Oversized Tee','tops','casual','unisex','red','S,M,L,XL,XXL',799.0,'casual','casual,oversized,bold',4.4,178,20,'https://crazymonk.in/cdn/shop/files/Red_1_60b5bf1b-6464-4cca-bb73-b0bd69700dd9.jpg?v=1751104940&width=1946','','v001','ThreadVerse'),
            (47,'Yellow Tie-Dye Tee','tops','casual','unisex','yellow','S,M,L,XL,XXL',899.0,'casual','casual,tie-dye,fun',4.1,145,20,'https://nohanger.com/cdn/shop/files/tiedyeyellowback.jpg?v=1750751681&width=3840','','v001','ThreadVerse'),
            (48,'Lavender Pastel Tee','tops','casual','unisex','lavender','S,M,L,XL,XXL',749.0,'casual','casual,pastel,soft',4.2,162,20,'https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1687521373_1980496.jpg?w=300&dpr=1','','v001','ThreadVerse'),
            (49,'Brown Vintage Print Tee','tops','casual','unisex','brown','S,M,L,XL,XXL',849.0,'casual','casual,vintage,print',4.3,138,20,'https://wtflex.in/cdn/shop/files/FallenFateAcidWashTeeWebsite1.jpg?v=1767865121&width=1445','','v001','ThreadVerse'),
            (50,'Burgundy Longline Tee','tops','casual','unisex','burgundy','S,M,L,XL,XXL',949.0,'casual','casual,longline,minimal',4.5,172,20,'https://m.media-amazon.com/images/I/71ASbFGGerL._AC_UY1100_.jpg','','v001','ThreadVerse'),
            (51,'Black Puffer Jacket','jackets','puffer','men','black','S,M,L,XL,XXL',3999.0,'winter','winter,puffer,warm',4.7,220,20,'https://www.jackjones.in/cdn/shop/files/901029701_g1.jpg?v=1745345782&width=1080','','v001','ThreadVerse'),
            (52,'Navy Wool Overcoat','jackets','coat','men','navy','S,M,L,XL,XXL',5499.0,'winter','winter,wool,formal',4.8,195,20,'https://xcdn.next.co.uk/common/items/default/default/itemimages/3_4Ratio/product/lge/B51763s.jpg?im=Resize,width=750','','v001','ThreadVerse'),
            (53,'Olive Parka Jacket','jackets','parka','men','olive','S,M,L,XL,XXL',4499.0,'winter','winter,parka,outdoor',4.6,178,20,'https://assets.ajio.com/medias/sys_master/root/20230213/HO0v/63ea5b56f997dde6f4a25245/-473Wx593H-410354065-7jm-MODEL.jpg','','v001','ThreadVerse'),
            (54,'Camel Overcoat','jackets','coat','men','camel','S,M,L,XL,XXL',5999.0,'winter','winter,overcoat,classic',4.7,165,20,'https://static.zara.net/assets/public/ed0e/1604/f3684f659d9d/e3879b33168a/04080125704-p/04080125704-p.jpg?ts=1768920126354&w=352','','v001','ThreadVerse'),
            (55,'Charcoal Bomber Jacket','jackets','bomber','men','charcoal','S,M,L,XL,XXL',3499.0,'winter','winter,bomber,streetwear',4.5,155,20,'https://assets.ajio.com/medias/sys_master/root1/20250923/B3iX/68d26b048bfb9009ac27c9be/-473Wx593H-442663063-charcoal-MODEL.jpg','','v001','ThreadVerse'),
            (56,'Brown Shearling Jacket','jackets','shearling','men','brown','S,M,L,XL,XXL',6499.0,'winter','winter,shearling,luxury',4.8,142,20,'https://assets.myntassets.com/h_1440,q_75,w_1080/v1/assets/images/25654588/2023/11/2/1d208e7c-24ed-44d3-8542-086357ccd27d1698909469873JeggingsMANGOWomenJacketsMANGOWomenTopsMANGOWomenSkirtsMANGO1.jpg','','v001','ThreadVerse'),
            (57,'Forest Green Quilted Jacket','jackets','quilted','men','forest green','S,M,L,XL,XXL',3299.0,'winter','winter,quilted,casual',4.4,132,20,'https://www.redrae.co.uk/images/barbour-long-powell-quilted-jacket-forest-mqu1437gn91.jpg','','v001','ThreadVerse'),
            (58,'Burgundy Varsity Jacket','jackets','varsity','men','burgundy','S,M,L,XL,XXL',3799.0,'winter','winter,varsity,retro',4.6,128,20,'https://uspoloassn.in/cdn/shop/files/1_0a4b9cd4-c761-428b-8e55-883e5032df0a.jpg','','v001','ThreadVerse'),
            (59,'Grey Peacoat','jackets','peacoat','men','grey','S,M,L,XL,XXL',4999.0,'winter','winter,peacoat,smart',4.7,148,20,'https://image.hm.com/assets/hm/dc/6f/dc6f936aa4f8b2b830c94aed5a4b4f11a9783c0b.jpg?imwidth=2160','','v001','ThreadVerse'),
            (60,'Tan Trench Coat','jackets','trench','men','tan','S,M,L,XL,XXL',5299.0,'winter','winter,trench,classic',4.6,138,20,'https://dqp736wsu6w3m.cloudfront.net/s3bucket/w1000/looks/2501/beige-trench-coat-dark-shirt-denim.jpg','','v001','ThreadVerse'),
            (61,'Camel Wool Coat','jackets','coat','women','camel','S,M,L,XL,XXL',5999.0,'winter','winter,wool,elegant',4.8,182,20,'https://i.pinimg.com/736x/de/7f/9e/de7f9eec2e2ad7d5337c05acf70ea91a.jpg','','v001','ThreadVerse'),
            (62,'Black Puffer Jacket','jackets','puffer','women','black','S,M,L,XL,XXL',3799.0,'winter','winter,puffer,warm',4.6,165,20,'https://assets.ajio.com/medias/sys_master/root/20231013/y3eE/65284835afa4cf41f53f8497/-473Wx593H-466702098-black-MODEL.jpg','','v001','ThreadVerse'),
            (63,'Dusty Pink Quilted Jacket','jackets','quilted','women','dusty rose','S,M,L,XL,XXL',3299.0,'winter','winter,quilted,feminine',4.5,145,20,'https://media2.newlookassets.com/i/newlook/941070572/womens/clothing/coats-jackets/pale-pink-soft-touch-quilted-jacket.jpg?strip=true&qlt=50&w=720','','v001','ThreadVerse'),
            (64,'Forest Green Parka','jackets','parka','women','forest green','S,M,L,XL,XXL',4299.0,'winter','winter,parka,outdoor',4.6,138,20,'https://www.newforestclothing.co.uk/cdn/shop/files/preview_images/videoframe_21689.png?v=1727097394','','v001','ThreadVerse'),
            (65,'Cream Teddy Coat','jackets','teddy','women','cream','S,M,L,XL,XXL',4799.0,'winter','winter,teddy,cozy',4.7,155,20,'https://encrypted-tbn3.gstatic.com/shopping?q=tbn:ANd9GcT-4p8QJijiSzLgmV_GItNIAi07LG1BETOKCUAm_uDMsbJy0jrL4T-z30xhr6Y_siSjWp5nGJWwwpD0dJ_qpxkrnDeeumEzq8YeWf0vyBAJUDLJu70PwNGedw&usqp=CAc','','v001','ThreadVerse'),
            (66,'Black Pencil Skirt','skirts','office','women','black','S,M,L,XL,XXL',1499.0,'office','office,pencil,formal',4.5,168,20,'https://www.berrylush.com/cdn/shop/files/1_82af1d6c-abe2-462f-beed-ba4ae5434e9a.jpg?v=1752842032','','v001','ThreadVerse'),
            (67,'Navy Midi Office Skirt','skirts','office','women','navy','S,M,L,XL,XXL',1699.0,'office','office,midi,smart',4.4,145,20,'https://www.lulus.com/images/product/xlarge/12481681_643987.jpg?w=375&hdpi=1','','v001','ThreadVerse'),
            (68,'Burgundy Satin Party Skirt','skirts','party','women','burgundy','S,M,L,XL,XXL',2099.0,'party','party,satin,night out',4.7,132,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRE86Pzn2zj3WWNMEAM3VscjMU6Syc9_IrupA&s','','v001','ThreadVerse'),
            (69,'Floral Print Midi Skirt','skirts','casual','women','multicolor','S,M,L,XL,XXL',1599.0,'casual','casual,floral,boho',4.4,122,20,'https://assets.myntassets.com/f_auto,q_auto:eco,dpr_1.3,w_158,c_limit,fl_progressive/v1/assets/images/2025/AUGUST/26/B6Bw1ngF_bae2c49cbc86479bb4ac552e43fc8bb4.jpg','','v001','ThreadVerse'),
            (70,'Beige Linen A-Line Skirt','skirts','casual','women','beige','S,M,L,XL,XXL',1399.0,'casual','casual,linen,summer',4.3,115,20,'https://i.etsystatic.com/5609612/r/il/8b0534/6918969010/il_fullxfull.6918969010_l7em.jpg','','v001','ThreadVerse'),
            (71,'White Classic Office Shirt','shirts','formal','women','white','S,M,L,XL,XXL',1499.0,'office','office,formal,classic',4.5,195,20,'https://assets.myntassets.com/h_1440,q_75,w_1080/v1/assets/images/19577030/2022/8/20/71b290d7-9b8b-404a-8579-a5057e6b0bc31661007459044StyleQuotientWomenWhiteClassicCasualShirt1.jpg','','v001','ThreadVerse'),
            (72,'Powder Blue Formal Shirt','shirts','formal','women','powder blue','S,M,L,XL,XXL',1599.0,'office','office,smart,feminine',4.4,175,20,'https://www.hancockfashion.com/cdn/shop/files/16083SBlueS_1_1024x1024.jpg?v=1734412813','','v001','ThreadVerse'),
            (73,'Blush Pink Silk Shirt','shirts','party','women','blush','S,M,L,XL,XXL',2299.0,'party','party,silk,elegant',4.7,158,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRuuSPZQNucawlY90Vb9vt2iX2SYp8trd_tsA&s','','v001','ThreadVerse'),
            (74,'Black Satin Party Shirt','shirts','party','women','black','S,M,L,XL,XXL',1999.0,'party','party,satin,night out',4.6,142,20,'https://babecouture.in/cdn/shop/files/BLACK_SATIN_SHIRT_2.jpg?v=1713959833','','v001','ThreadVerse'),
            (75,'Cream Linen Casual Shirt','shirts','casual','women','cream','S,M,L,XL,XXL',1399.0,'casual','casual,linen,relaxed',4.3,128,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR2ll17Ig0FVZ3sMUQxJJdD3pbIbb6sjRAsWQ&s','','v001','ThreadVerse'),
            (76,'Olive Oversized Casual Shirt','shirts','casual','women','olive','S,M,L,XL,XXL',1299.0,'casual','casual,oversized,everyday',4.2,115,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR9YZI6JFKOuWUjj_NXnPZ6xuVzjdmRcHp75Q&s','','v001','ThreadVerse'),
            (77,'Navy Striped Shirt','shirts','formal','women','navy','S,M,L,XL,XXL',1499.0,'office','office,stripes,smart',4.4,138,20,'https://imagescdn.allensolly.com/img/app/product/7/758823-8663735.jpg?auto=format&w=390','','v001','ThreadVerse'),
            (78,'Lavender Casual Shirt','shirts','casual','women','lavender','S,M,L,XL,XXL',1199.0,'casual','casual,pastel,soft',4.2,105,20,'https://assets.myntassets.com/w_360,q_50,,dpr_2,fl_progressive,f_webp/assets/images/14615002/2021/8/3/4df70017-a3d6-4ac9-9534-d98d5e10cd0d1627984679526-Roadster-Women-Pink-Casual-Shirt-8381627984678748-1.jpg','','v001','ThreadVerse'),
            (79,'Red Tie-Front Shirt','shirts','casual','women','red','S,M,L,XL,XXL',1599.0,'casual','casual,tie front,fun',4.3,122,20,'https://m.media-amazon.com/images/I/71vnlZoP8SL._AC_UY1100_.jpg','','v001','ThreadVerse'),
            (80,'Sage Green Office Shirt','shirts','formal','women','sage green','S,M,L,XL,XXL',1699.0,'office','office,formal,smart',4.5,148,20,'https://stylequotient.co.in/cdn/shop/files/SS24SQARTHASAT_SG-6.jpg?v=1727155701','','v001','ThreadVerse'),
            (81,'Black Formal Blazer','blazers','formal','unisex','black','S,M,L,XL,XXL',3999.0,'office','office,formal,power',4.7,215,20,'https://img.freepik.com/premium-psd/black-blazer-mockup-psd_53876-599809.jpg?semt=ais_incoming&w=740&q=80','','v001','ThreadVerse'),
            (82,'Navy Single Breasted Blazer','blazers','formal','unisex','navy','S,M,L,XL,XXL',3799.0,'office','office,classic,smart',4.6,192,20,'https://img01.ztat.net/article/spp-media-p1/c5f9c0bee92e44e8b92ec15e71733182/f5c987e7bebf4b17aff66afc234e6bad.jpg?imwidth=762&filter=packshot','','v001','ThreadVerse'),
            (83,'Charcoal Slim Fit Blazer','blazers','formal','unisex','charcoal','S,M,L,XL,XXL',4199.0,'office','office,slim fit,formal',4.5,178,20,'https://d1fufvy4xao6k9.cloudfront.net/feed/img/man_jacket/989791/without_model_small.png','','v001','ThreadVerse'),
            (84,'Camel Oversized Blazer','blazers','casual','unisex','camel','S,M,L,XL,XXL',3499.0,'casual','casual,oversized,trendy',4.6,165,20,'https://www.everlane.com/cdn/shop/files/889133c6_9283.jpg?v=1753411590&width=1000','','v001','ThreadVerse'),
            (85,'White Linen Blazer','blazers','casual','unisex','white','S,M,L,XL,XXL',2999.0,'casual','casual,linen,summer',4.4,148,20,'https://image.hm.com/assets/hm/d5/e0/d5e0b5c9a139b5c0019d8262d023423c388da54d.jpg?imwidth=1260','','v001','ThreadVerse'),
            (86,'Burgundy Party Blazer','blazers','party','unisex','burgundy','S,M,L,XL,XXL',3799.0,'party','party,festive,bold',4.7,138,20,'https://thefrankieshop.com/cdn/shop/files/JUN-PADDED-BLAZER-BURGUNDY-8585_be5af3ca-9f47-478c-bef4-384963e5ab48.jpg?v=1756472366&width=1200','','v001','ThreadVerse'),
            (87,'Sage Green Casual Blazer','blazers','casual','unisex','sage green','S,M,L,XL,XXL',3299.0,'casual','casual,relaxed,smart',4.5,132,20,'https://xcdn.next.co.uk/common/items/default/default/itemimages/3_4Ratio/product/lge/E93122s6.jpg?im=Resize,width=750','','v001','ThreadVerse'),
            (88,'Dusty Pink Blazer','blazers','party','unisex','dusty rose','S,M,L,XL,XXL',3599.0,'party','party,soft,elegant',4.6,125,20,'https://images.express.com/is/image/expressfashion/0039_04354217_0736_a001?cache=on&wid=480&fmt=jpeg&qlt=85,1&resmode=sharp2&op_usm=1,1,5,0&defaultImage=Photo-Coming-Soon','','v001','ThreadVerse'),
            (89,'Olive Double Breasted Blazer','blazers','casual','unisex','olive','S,M,L,XL,XXL',3999.0,'casual','casual,double breasted,bold',4.5,118,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQWg6SkynjRvDK8pDhUN4kL7EwV70mAjQeQ9g&s','','v001','ThreadVerse'),
            (90,'Grey Pinstripe Blazer','blazers','formal','unisex','grey','S,M,L,XL,XXL',4299.0,'office','office,pinstripe,classic',4.7,142,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS12kdYuIN6fHl85uKtf0UOLrj0W5-Lk5IPew&s','','v001','ThreadVerse'),
            (91,'White Sleeveless Office Top','tops','formal','women','white','S,M,L,XL,XXL',999.0,'office','office,sleeveless,smart',4.4,175,20,'https://imagescdn.vanheusenindia.com/img/app/product/3/39827511-16462832.jpg?auto=format&w=390','','v001','ThreadVerse'),
            (92,'Black Turtleneck Top','tops','formal','women','black','S,M,L,XL,XXL',1199.0,'office','office,turtleneck,minimal',4.5,162,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQmua_67rdtQGSUFicNZnncg0ezp469gnY1cA&s','','v001','ThreadVerse'),
            (93,'Cobalt Blue Peplum Top','tops','party','women','cobalt blue','S,M,L,XL,XXL',1499.0,'party','party,peplum,elegant',4.6,148,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSLQaIMwLkpbc-ADzysoK8AsU7ik0vDU1P9Jg&s','','v001','ThreadVerse'),
            (94,'Gold Sequin Party Top','tops','party','women','gold','S,M,L,XL,XXL',1799.0,'party','party,sequin,festive',4.8,138,20,'https://static.zara.net/assets/public/7e09/24e1/f5f842eda0d3/1b2dc3d5c9a0/00881066303-p/00881066303-p.jpg?ts=1774014478377&w=352','','v001','ThreadVerse'),
            (95,'Blush Pink Ruffle Top','tops','party','women','blush','S,M,L,XL,XXL',1399.0,'party','party,ruffle,feminine',4.5,128,20,'https://media.landmarkshops.in/cdn-cgi/image/h=730,w=540,q=85,fit=cover/lifestyle/1000015098241-Pink-LightPink-1000015098241_02-2100.jpg','','v001','ThreadVerse'),
            (96,'Cream Casual Knit Top','tops','casual','women','cream','S,M,L,XL,XXL',1099.0,'casual','casual,knit,cozy',4.3,118,20,'https://media2.newlookassets.com/i/newlook/933953414/womens/clothing/knitwear/cream-ribbed-knit-raglan-sleeve-cardigan.jpg?strip=true&qlt=50&w=720','','v001','ThreadVerse'),
            (97,'Sage Green Cami Top','tops','casual','women','sage green','S,M,L,XL,XXL',899.0,'casual','casual,cami,summer',4.2,108,20,'https://i.pinimg.com/564x/c7/2a/7d/c72a7d34bbb0807af9d9c0469c3f7a55.jpg','','v001','ThreadVerse'),
            (98,'Lavender Lace Trim Top','tops','casual','women','lavender','S,M,L,XL,XXL',1299.0,'casual','casual,lace,feminine',4.4,115,20,'https://cdn-images.farfetch-contents.com/25/24/67/46/25246746_56777369_600.jpg','','v001','ThreadVerse'),
            (99,'Terracotta Crop Top','tops','casual','women','terracotta','S,M,L,XL,XXL',999.0,'casual','casual,crop,trendy',4.3,122,20,'https://assets.myntassets.com/h_1440,q_75,w_1080/v1/assets/images/28191328/2024/4/22/5012ae17-dd00-48a2-9dd9-c708c0b16f841713782027392-DressBerry-Terracotta-Ring--Wrap-Top-4141713782026793-1.jpg','','v001','ThreadVerse'),
            (100,'Navy Bardot Top','tops','party','women','navy','S,M,L,XL,XXL',1499.0,'party','party,bardot,off shoulder',4.6,135,20,'https://basicouture.com/cdn/shop/files/OffShoulderNavy.jpg?v=1767720111&width=2000','','v001','ThreadVerse'),
            (101,'Black Leather Tote Bag','bags','tote','women','black','One Size',2999.0,'office','office,leather,tote',4.7,195,20,'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRh3RqZMdMcxatW1GgI3CqE6FVltzkdx4bbgQ&s','','v001','ThreadVerse'),
            (102,'Tan Crossbody Bag','bags','crossbody','women','tan','One Size',1999.0,'casual','casual,crossbody,everyday',4.5,172,20,'https://images.unsplash.com/photo-1760624294699-3d3156314391?w=600&auto=format&fit=crop&q=60','','v001','ThreadVerse'),
            (103,'Burgundy Evening Clutch','bags','clutch','women','burgundy','One Size',1499.0,'party','party,clutch,evening',4.6,155,20,'https://xcdn.next.co.uk/common/items/default/default/itemimages/3_4Ratio/product/lge/AJ7694s.jpg?im=Resize,width=750','','v001','ThreadVerse'),
            (104,'Cream Mini Shoulder Bag','bags','shoulder','women','cream','One Size',2499.0,'casual','casual,mini,chic',4.4,138,20,'https://www.fizzygoblet.com/cdn/shop/files/CreamCrossbodydomesticwhitebg-3_11zon.jpg?v=1688542437&width=600','','v001','ThreadVerse'),
            (105,'Cobalt Blue Structured Bag','bags','structured','women','cobalt blue','One Size',2799.0,'office','office,structured,bold',4.5,128,20,'https://saumyasstores.com/cdn/shop/files/51hSXO0kKRL.jpg?v=1766744667&width=1445','','v001','ThreadVerse'),
            (106,'Gold Statement Necklace','accessories','jewellery','women','gold','One Size',999.0,'party','party,statement,jewellery',4.6,165,20,'https://i5.walmartimages.com/seo/Exaggerated-Statement-Metal-Sphere-Pendant-Necklace-for-Women-Unique-Multi-layer-Vintage-Necklace-Fashion-Trendy-Retro-Gold-Beaded-Chain-Necklace_da5ad04c-b883-4349-b362-64657e6401d7.997c3305900c55ffa737e206fde0a114.jpeg?odnHeight=768&odnWidth=768&odnBg=FFFFFF','','v001','ThreadVerse'),
            (107,'Pearl Stud Earrings','accessories','jewellery','women','white','One Size',599.0,'office','office,classic,pearl',4.7,188,20,'https://www.mannash.in/cdn/shop/products/MCYES370D809_1.jpg?v=1657800563','','v001','ThreadVerse'),
            (108,'Silk Hair Scarf','accessories','scarves','women','multicolor','One Size',799.0,'casual','casual,hair,scarf',4.4,142,20,'https://m.media-amazon.com/images/I/61C3E38HlBL._AC_UY1100_.jpg','','v001','ThreadVerse'),
            (109,'Tortoiseshell Sunglasses','accessories','eyewear','women','brown','One Size',1299.0,'casual','casual,summer,sunglasses',4.5,155,20,'https://www.buyhautesauce.com/cdn/shop/files/AW24_HSSG2557_1_d6ab4f7a-de9b-4eeb-86a1-cf44330b62c1.jpg?v=1716279790','','v001','ThreadVerse'),
            (110,'Beige Canvas Tote Bag','bags','tote','women','beige','One Size',1499.0,'casual','casual,canvas,everyday',4.3,132,20,'https://kotart.in/cdn/shop/products/Kotart-Kotart-Graphic-Printed-Cotton-Tote-Bag-for-Women-Reusable-Cute-Printed-Shopping-Grocery-Bag-Multipurpose-Canvas-Shopping-Tote-Bag-with-Long-Handle-15-x-16-inch-Natural-Beige.jpg?v=1697550048','','v001','ThreadVerse'),
        ]
        cur.executemany("""INSERT OR IGNORE INTO products
            (id,name,category,subcategory,gender,color,sizes,price,occasion,tags,
             rating,reviews,stock,image,description,vendor_id,vendor_name)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", products)

    conn.commit()
    conn.close()


# ── Domain helpers ────────────────────────────────────────────────────────────

def row_to_product(row):
    if not row:
        return None
    p = dict(row)
    p['sizes']  = [s.strip() for s in (p.get('sizes') or '').split(',') if s.strip()]
    p['tags']   = [t.strip() for t in (p.get('tags')  or '').split(',') if t.strip()]
    p['price']  = float(p['price'])
    p['rating'] = float(p.get('rating') or 0)
    return p


def get_products(category=None, gender=None, search=None, max_price=None,
                 sort='default', vendor_id=None):
    where, args = [], []
    if category:  where.append("category = ?");              args.append(category)
    if vendor_id: where.append("vendor_id = ?");             args.append(vendor_id)
    if gender:    where.append("gender IN (?, 'unisex')");   args.append(gender)
    if max_price: where.append("price <= ?");                args.append(max_price)
    if search:
        where.append("(name LIKE ? OR tags LIKE ? OR description LIKE ?)")
        like = f'%{search}%'
        args += [like, like, like]
    sql = "SELECT * FROM products"
    if where:
        sql += " WHERE " + " AND ".join(where)
    order = {'price_asc': 'price ASC', 'price_desc': 'price DESC',
             'rating': 'rating DESC'}.get(sort, 'id ASC')
    sql += f" ORDER BY {order}"
    return [row_to_product(r) for r in query(sql, args)]


def get_product(pid):
    return row_to_product(query_one("SELECT * FROM products WHERE id=?", (pid,)))


def get_user_by_email(email):
    return query_one("SELECT * FROM users WHERE email=?", (email,))


def get_user_by_id(uid):
    return query_one("SELECT * FROM users WHERE id=?", (uid,))


def hash_password(plain: str) -> str:
    return generate_password_hash(plain)


def verify_password(plain: str, stored: str) -> bool:
    if stored and (stored.startswith('pbkdf2:') or stored.startswith('scrypt:')):
        return check_password_hash(stored, plain)
    return plain == stored


def create_user(uid, name, email, password, role, shop_name, created,
                contact_number=None, verification_doc=None, google_id=None):
    hashed = hash_password(password) if password else ''
    execute(
        """INSERT INTO users
           (id,name,email,password,role,shop_name,created,contact_number,verification_doc,google_id)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (uid, name, email, hashed, role, shop_name, created,
         contact_number or '', verification_doc or '', google_id or '')
    )


def get_or_create_google_user(google_id: str, email: str, name: str):
    import uuid, datetime as _dt
    user = query_one("SELECT * FROM users WHERE google_id=?", (google_id,))
    if user:
        return user
    user = query_one("SELECT * FROM users WHERE email=?", (email,))
    if user:
        execute("UPDATE users SET google_id=? WHERE id=?", (google_id, user['id']))
        return query_one("SELECT * FROM users WHERE id=?", (user['id'],))
    uid     = 'u' + str(uuid.uuid4())[:6]
    created = _dt.datetime.now().strftime('%d %b %Y')
    execute(
        """INSERT INTO users
           (id,name,email,password,role,shop_name,created,contact_number,verification_doc,google_id)
           VALUES (?,'','customer','',?,?,?)""",
        (uid, name, email, created, google_id)  # fixed arg count
    )
    # Rewrite with correct columns
    execute("DELETE FROM users WHERE id=?", (uid,))
    execute(
        """INSERT INTO users
           (id,name,email,password,role,shop_name,created,contact_number,verification_doc,google_id)
           VALUES (?,?,?,'','customer','',?,?,?,?)""",
        (uid, name, email, created, '', '', google_id)
    )
    return query_one("SELECT * FROM users WHERE id=?", (uid,))


def get_cart(session_id):
    rows = query("SELECT * FROM cart WHERE session_id=?", (session_id,))
    for r in rows:
        r['price'] = float(r['price'])
    return rows


def cart_add(session_id, product, size):
    existing = query_one(
        "SELECT id, qty FROM cart WHERE session_id=? AND product_id=?",
        (session_id, product['id'])
    )
    if existing:
        execute("UPDATE cart SET qty=qty+1 WHERE id=?", (existing['id'],))
    else:
        execute(
            "INSERT INTO cart (session_id,product_id,name,price,qty,selected_size,image) VALUES (?,?,?,?,1,?,?)",
            (session_id, product['id'], product['name'], product['price'],
             size, product.get('image', ''))
        )


def cart_remove(session_id, product_id):
    execute("DELETE FROM cart WHERE session_id=? AND product_id=?", (session_id, product_id))


def cart_update(session_id, product_id, qty):
    if qty <= 0:
        cart_remove(session_id, product_id)
    else:
        execute("UPDATE cart SET qty=? WHERE session_id=? AND product_id=?",
                (qty, session_id, product_id))


def cart_clear(session_id):
    execute("DELETE FROM cart WHERE session_id=?", (session_id,))


def get_wishlist(session_id):
    rows = query("SELECT * FROM wishlist WHERE session_id=?", (session_id,))
    for r in rows:
        r['price'] = float(r['price'])
    return rows


def wishlist_toggle(session_id, product):
    existing = query_one(
        "SELECT id FROM wishlist WHERE session_id=? AND product_id=?",
        (session_id, product['id'])
    )
    if existing:
        execute("DELETE FROM wishlist WHERE id=?", (existing['id'],))
        return False
    else:
        execute(
            "INSERT INTO wishlist (session_id,product_id,name,price,image) VALUES (?,?,?,?,?)",
            (session_id, product['id'], product['name'],
             product['price'], product.get('image', ''))
        )
        return True


def get_orders_for_user(user_id):
    orders = query("SELECT * FROM orders WHERE user_id=? ORDER BY date DESC", (user_id,))
    for o in orders:
        o['total']    = float(o['total'])
        o['items']    = _get_order_items(o['id'])
        o['shipping'] = {
            'name':    o.pop('shipping_name', ''),
            'address': o.pop('shipping_address', ''),
            'city':    o.pop('shipping_city', '')
        }
    return orders


def get_orders_for_vendor(vendor_id):
    prod_ids = [r['id'] for r in query("SELECT id FROM products WHERE vendor_id=?", (vendor_id,))]
    if not prod_ids:
        return []
    placeholders = ','.join(['?'] * len(prod_ids))
    order_ids = [r['order_id'] for r in query(
        f"SELECT DISTINCT order_id FROM order_items WHERE product_id IN ({placeholders})", prod_ids
    )]
    if not order_ids:
        return []
    results = []
    for oid in order_ids:
        o = query_one("SELECT * FROM orders WHERE id=?", (oid,))
        if not o:
            continue
        o['total']     = float(o['total'])
        all_items      = _get_order_items(oid)
        o['items']     = [i for i in all_items if i.get('product_id') in prod_ids]
        o['total']     = sum(i['price'] * i.get('qty', 1) for i in o['items'])
        o['shipping']  = {
            'name':    o.pop('shipping_name', ''),
            'address': o.pop('shipping_address', ''),
            'city':    o.pop('shipping_city', '')
        }
        results.append(o)
    return results


def _get_order_items(order_id):
    rows = query("SELECT * FROM order_items WHERE order_id=?", (order_id,))
    for r in rows:
        r['price'] = float(r['price'])
    return rows


def create_order(order_id, user_id, items, total, status, date, shipping):
    execute(
        "INSERT INTO orders (id,user_id,total,status,date,shipping_name,shipping_address,shipping_city) VALUES (?,?,?,?,?,?,?,?)",
        (order_id, user_id, total, status, date,
         shipping.get('name', ''), shipping.get('address', ''), shipping.get('city', ''))
    )
    for item in items:
        product_id = item.get('product_id') or item.get('id')
        qty        = int(item.get('qty', 1) or 1)
        execute(
            "INSERT INTO order_items (order_id,product_id,name,price,qty,selected_size,image) VALUES (?,?,?,?,?,?,?)",
            (order_id, product_id, item['name'], item['price'],
             qty, item.get('selected_size', 'M'), item.get('image', ''))
        )
        # Reduce stock (clamp to 0)
        execute(
            "UPDATE products SET stock=MAX(stock-?,0) WHERE id=?",
            (qty, product_id)
        )


def get_vendor_stats(vendor_id):
    prods    = query("SELECT id FROM products WHERE vendor_id=?", (vendor_id,))
    prod_ids = [p['id'] for p in prods]
    total_products = len(prod_ids)
    if not prod_ids:
        return total_products, 0, 0
    placeholders = ','.join(['?'] * len(prod_ids))
    order_ids = {r['order_id'] for r in query(
        f"SELECT DISTINCT order_id FROM order_items WHERE product_id IN ({placeholders})", prod_ids
    )}
    total_orders = len(order_ids)
    if not order_ids:
        return total_products, 0, 0
    op       = ','.join(['?'] * len(order_ids))
    rev_rows = query(
        f"SELECT price, qty FROM order_items WHERE order_id IN ({op}) AND product_id IN ({placeholders})",
        list(order_ids) + prod_ids
    )
    total_revenue = sum(float(r['price']) * r.get('qty', 1) for r in rev_rows)
    return total_products, total_orders, round(total_revenue, 2)
