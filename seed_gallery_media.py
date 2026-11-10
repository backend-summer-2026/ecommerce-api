import os
import sys
import urllib.request
import django

# Django muhitini yuklash
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from apps.products.models import Product, ProductMedia, ProductVariant

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media', 'products', '2026', '01')
os.makedirs(MEDIA_DIR, exist_ok=True)

def download_image(url: str, filename: str) -> str:
    dest_path = os.path.join(MEDIA_DIR, filename)
    if not os.path.exists(dest_path) or os.path.getsize(dest_path) < 1000:
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp, open(dest_path, 'wb') as out:
                out.write(resp.read())
            print(f"Downloaded: {filename}")
        except Exception as e:
            print(f"Failed to download {url} for {filename}: {e}")
    return f"products/2026/01/{filename}"

GALLERY_DATA = {
    'iphone-15-pro-max': [
        ('https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?w=800&q=80', 'Ekran va Dynamic Island'),
        ('https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=800&q=80', 'Titan qirra va orqa panel'),
    ],
    'iphone-15-pro': [
        ('https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?w=800&q=80', 'Displey ko\'rinishi'),
        ('https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=800&q=80', 'Yon tomoni va titan ramka'),
    ],
    'iphone-15': [
        ('https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=800&q=80', 'Orqa mat oyna'),
        ('https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?w=800&q=80', 'Super Retina displey'),
    ],
    'samsung-galaxy-s24-ultra': [
        ('https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=800&q=80', 'S-Pen stilus bilan'),
        ('https://images.unsplash.com/photo-1580910051074-3eb694886505?w=800&q=80', 'Orqa 200MP kamera tizimi'),
    ],
    'samsung-galaxy-z-fold5': [
        ('https://images.unsplash.com/photo-1580910051074-3eb694886505?w=800&q=80', 'Ochiq holatdagi 7.6 dyuym ekran'),
        ('https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=800&q=80', 'Yopiq qulay shakli'),
    ],
    'xiaomi-14-ultra': [
        ('https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=800&q=80', 'Leica kamera doirasi'),
        ('https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800&q=80', 'Charm teksturali orqa korpus'),
    ],
    'google-pixel-8-pro': [
        ('https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800&q=80', 'Kamera visor chizig\'i'),
        ('https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=800&q=80', 'Yassi OLED displey'),
    ],
    'macbook-pro-16-m3-max': [
        ('https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=800&q=80', 'Ochiq 120Hz Liquid Retina ekrani'),
        ('https://images.unsplash.com/photo-1541807084-5c52b6b3adef?w=800&q=80', 'Magic Keyboard va trekpad'),
        ('https://images.unsplash.com/photo-1525547719571-a2d4ac8945e2?w=800&q=80', 'Yon tomon portlari va MagSafe'),
    ],
    'macbook-air-15-m3': [
        ('https://images.unsplash.com/photo-1611186871348-b1ce696e52c9?w=800&q=80', 'Yupqa profili'),
        ('https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=800&q=80', 'Ish stolidagi ko\'rinishi'),
    ],
    'asus-rog-zephyrus-g16': [
        ('https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=800&q=80', 'OLED ekran va RGB klaviatura'),
        ('https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=800&q=80', 'Orqa Slash Lighting yorug\'ligi'),
    ],
    'lenovo-thinkpad-x1-carbon-gen-12': [
        ('https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=800&q=80', 'TrackPoint va premium klaviatura'),
        ('https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=800&q=80', 'Uglerod tolali engil qopqoq'),
    ],
    'dell-xps-15': [
        ('https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=800&q=80', 'InfinityEdge 4-tomonlama romsiz ekran'),
        ('https://images.unsplash.com/photo-1541807084-5c52b6b3adef?w=800&q=80', 'Shishali keng trekpad'),
    ],
    'sony-wh-1000xm5': [
        ('https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&q=80', 'Yumshoq charm yostiqchalar'),
        ('https://images.unsplash.com/photo-1484704849700-f032a568e944?w=800&q=80', 'Kiyilgan holatdagi zamonaviy dizayn'),
        ('https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=800&q=80', 'Ixcham himoya g\'ilofi'),
    ],
    'airpods-pro-2': [
        ('https://images.unsplash.com/photo-1600294037681-c80b4cb5b434?w=800&q=80', 'MagSafe g\'ilofi va quloqchinlar'),
        ('https://images.unsplash.com/photo-1588423771073-b8903fbb85b5?w=800&q=80', 'Silikon nasadkalari bilan'),
    ],
    'airpods-max': [
        ('https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=800&q=80', 'Smart Case g\'ilofida'),
        ('https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&q=80', 'Tafsilotli po\'lat kamon'),
    ],
    'galaxy-buds-2-pro': [
        ('https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=800&q=80', 'Kompakt zaryadlash qutisi'),
        ('https://images.unsplash.com/photo-1600294037681-c80b4cb5b434?w=800&q=80', 'Ergonomik shakli'),
    ],
    'jbl-charge-5': [
        ('https://images.unsplash.com/photo-1545454675-3531b543be5d?w=800&q=80', 'Suv o\'tkazmaydigan himoyasi'),
        ('https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=800&q=80', 'Passiv bas radiatorlari'),
    ],
    'marshall-emberton-2': [
        ('https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=800&q=80', 'Vintage panjara va oltin tugma'),
        ('https://images.unsplash.com/photo-1545454675-3531b543be5d?w=800&q=80', 'Mustahkam silikon qobiq'),
    ],
    'apple-watch-ultra-2': [
        ('https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?w=800&q=80', 'Titan qirra va apelsinrang Action tugma'),
        ('https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&q=80', 'Alpine Loop tasmasi bilan'),
    ],
    'apple-watch-series-9': [
        ('https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&q=80', 'Always-On Retina ekrani'),
        ('https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?w=800&q=80', 'Sport Loop tasmasi'),
    ],
    'galaxy-watch-6-classic': [
        ('https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&q=80', 'Aylanuvchi mexanik ramka'),
        ('https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?w=800&q=80', 'Klassik charm tasma bilan'),
    ],
    'xiaomi-smart-band-8-pro': [
        ('https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?w=800&q=80', 'Katta AMOLED ekran'),
    ],
    'ipad-pro-13-m4': [
        ('https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=800&q=80', 'Ultra yupqa 5.1mm korpus'),
        ('https://images.unsplash.com/photo-1561154464-82e9adf32764?w=800&q=80', 'Apple Pencil Pro bilan ishlash'),
    ],
    'galaxy-tab-s9-ultra': [
        ('https://images.unsplash.com/photo-1561154464-82e9adf32764?w=800&q=80', '14.6 dyuymli Dynamic AMOLED ekrani'),
        ('https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=800&q=80', 'S-Pen va klaviatura bilan'),
    ],
    'playstation-5-slim': [
        ('https://images.unsplash.com/photo-1606813907291-d86efa9b94db?w=800&q=80', 'DualSense pulti va konsol'),
        ('https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=800&q=80', 'Vertikal taglikdagi ko\'rinishi'),
    ],
    'nike-air-force-1': [
        ('https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=800&q=80', 'Yon tomon Swoosh belgisi'),
        ('https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80', 'Mustahkam kauchuk taglik'),
    ],
    'nike-air-max-270': [
        ('https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80', 'Katta havo yostig\'i (Air Unit)'),
        ('https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=800&q=80', 'Nafas oluvchi to\'rli yuqori qism'),
    ],
    'adidas-samba-og': [
        ('https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=800&q=80', 'T-burun zamsh va klassik taglik'),
        ('https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=800&q=80', '3 ta chiziq va oltin Samba yozuvi'),
    ],
    'adidas-ultraboost-light': [
        ('https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=800&q=80', 'Light Boost amortizatsiya tagligi'),
        ('https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80', 'Continental kauchuk tutqichi'),
    ],
    'puma-rs-x': [
        ('https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80', 'Rang-barang retro qatlamlar'),
    ],
    'nike-club-fleece-hoodie': [
        ('https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800&q=80', 'Kapushon va keng old cho\'ntak'),
    ],
    'adidas-tracksuit': [
        ('https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800&q=80', 'Sport uslubidagi to\'liq komplekt'),
    ],
    'dyson-v15-detect': [
        ('https://images.unsplash.com/photo-1558317374-067fb5f30001?w=800&q=80', 'Lazerli Fluffy cho\'tkasi va nasadkalar'),
        ('https://images.unsplash.com/photo-1527515637462-cff94eecc1ac?w=800&q=80', 'LCD ekran va chang hisoblagichi'),
    ],
    'xiaomi-robot-vacuum-x10': [
        ('https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80', 'Avtomatik bo\'shatish stansiyasi'),
        ('https://images.unsplash.com/photo-1558317374-067fb5f30001?w=800&q=80', 'LiDAR navigatsiya va nam tozalash'),
    ],
    'delonghi-magnifica-s': [
        ('https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=800&q=80', 'Espresso quyilishi va qahva donalari'),
        ('https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=800&q=80', 'Kapuchinator va boshqaruv paneli'),
    ],
}

@transaction.atomic
def seed_gallery():
    print("--- Mahsulotlarga qo'shimcha galereya rasmlarini qo'shish ---")
    added_count = 0
    for slug, img_list in GALLERY_DATA.items():
        try:
            prod = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            print(f"Product not found: {slug}")
            continue

        variants = list(prod.variants.all())

        for idx, (url, alt) in enumerate(img_list, start=2):
            filename = f"{slug}-gallery-{idx}.jpg"
            file_path = download_image(url, filename)
            
            # Variantga ham bog'lash (agar bir nechta variant bo'lsa)
            target_variant = variants[idx - 2] if len(variants) >= (idx - 1) else None

            media_obj, created = ProductMedia.objects.get_or_create(
                product=prod,
                file=file_path,
                defaults={
                    'alt_text': f"{prod.name} - {alt}",
                    'media_type': ProductMedia.MediaType.IMAGE,
                    'is_main': False,
                    'order': idx,
                    'variant': target_variant,
                }
            )
            if created:
                added_count += 1
                print(f"Added gallery image #{idx} for {prod.name}")

    print(f"\nJami qo'shilgan yangi galereya rasmlari: {added_count}")
    print(f"Hozirda umumiy ProductMedia soni: {ProductMedia.objects.count()}")

if __name__ == '__main__':
    seed_gallery()
