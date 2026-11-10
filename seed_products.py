import os
import sys
import urllib.request
from decimal import Decimal
import django

# Django muhitini yuklash
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from django.utils.text import slugify
from apps.products.models import (
    Category,
    Brand,
    Product,
    ProductCategory,
    ProductVariant,
    Attribute,
    AttributeValue,
    ProductVariantAttributeValue,
    ProductMedia,
    Inventory,
)
from apps.reviews.models import Review, ReviewStatus, ProductRatingSummary
from apps.users.models import User

# Rasmlar saqlanadigan papka
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

@transaction.atomic
def seed():
    print("--- 1. Kategoriyalarni yaratish ---")
    cat_electronics, _ = Category.objects.get_or_create(
        slug='electronics', defaults={'name': 'Electronics', 'description': 'Zamonaviy elektronika va gadjetlar'}
    )
    cat_computers, _ = Category.objects.get_or_create(
        slug='computers', parent=cat_electronics, defaults={'name': 'Computers', 'description': 'Kompyuterlar va uning qismlari'}
    )
    cat_laptops, _ = Category.objects.get_or_create(
        slug='laptops', parent=cat_computers, defaults={'name': 'Laptops', 'description': 'Noutbuklar va ultrabuklar'}
    )
    cat_smartphones, _ = Category.objects.get_or_create(
        slug='smartphones', parent=cat_electronics, defaults={'name': 'Smartphones', 'description': 'Smartfonlar va telefonlar'}
    )
    cat_audio, _ = Category.objects.get_or_create(
        slug='audio', parent=cat_electronics, defaults={'name': 'Audio & Headphones', 'description': 'Quloqchinlar, dinamiklar va akustika'}
    )
    cat_wearables, _ = Category.objects.get_or_create(
        slug='wearables', parent=cat_electronics, defaults={'name': 'Smart Watches & Wearables', 'description': 'Aqlli soatlar va fitnes bilaguzuklar'}
    )
    cat_tablets, _ = Category.objects.get_or_create(
        slug='tablets', parent=cat_electronics, defaults={'name': 'Tablets', 'description': 'Planshetlar va aksessuarlar'}
    )
    cat_gaming, _ = Category.objects.get_or_create(
        slug='gaming', parent=cat_electronics, defaults={'name': 'Gaming & Consoles', 'description': 'O\'yin konsollari va geyming jihozlari'}
    )

    cat_fashion, _ = Category.objects.get_or_create(
        slug='fashion', defaults={'name': 'Fashion', 'description': 'Zamonaviy kiyim-kechak va poyabzallar'}
    )
    cat_footwear, _ = Category.objects.get_or_create(
        slug='footwear', parent=cat_fashion, defaults={'name': 'Footwear', 'description': 'Krossovkalar, tufli va poyabzallar'}
    )
    cat_clothing, _ = Category.objects.get_or_create(
        slug='clothing', parent=cat_fashion, defaults={'name': 'Clothing & Apparel', 'description': 'Ust-bosh, xudi, sport kiyimlari'}
    )

    cat_home, _ = Category.objects.get_or_create(
        slug='home-appliances', defaults={'name': 'Home Appliances & Living', 'description': 'Maishiy texnika va uy jihozlari'}
    )
    cat_cleaning, _ = Category.objects.get_or_create(
        slug='smart-cleaning', parent=cat_home, defaults={'name': 'Smart Cleaning', 'description': 'Changyutgichlar va tozalash vositalari'}
    )
    cat_kitchen, _ = Category.objects.get_or_create(
        slug='kitchen-coffee', parent=cat_home, defaults={'name': 'Kitchen & Coffee', 'description': 'Oshxona texnikasi va qahva mashinalari'}
    )

    print("--- 2. Brendlarni yaratish ---")
    brands_data = [
        ('Apple', 'apple', 'https://www.apple.com', 'Apple Inc. premium consumer tech'),
        ('Samsung', 'samsung', 'https://www.samsung.com', 'Samsung Electronics Corporation'),
        ('Sony', 'sony', 'https://www.sony.com', 'Sony multimedia and entertainment electronics'),
        ('Nike', 'nike', 'https://www.nike.com', 'Nike athletic apparel and footwear'),
        ('Adidas', 'adidas', 'https://www.adidas.com', 'Adidas iconic sportswear and sneakers'),
        ('Xiaomi', 'xiaomi', 'https://www.mi.com', 'Xiaomi smart consumer tech and phones'),
        ('ASUS', 'asus', 'https://www.asus.com', 'ASUS laptops, motherboards and ROG gaming gear'),
        ('Lenovo', 'lenovo', 'https://www.lenovo.com', 'Lenovo personal computing and ThinkPad devices'),
        ('Puma', 'puma', 'https://www.puma.com', 'Puma athletic apparel and lifestyle gear'),
        ('Dyson', 'dyson', 'https://www.dyson.com', 'Dyson innovative air care and vacuum appliances'),
        ('JBL', 'jbl', 'https://www.jbl.com', 'JBL high-performance audio systems'),
        ('Marshall', 'marshall', 'https://www.marshallheadphones.com', 'Marshall legendary vintage audio systems'),
        ('Google', 'google', 'https://store.google.com', 'Google Pixel phones and smart ecosystem'),
        ('Dell', 'dell', 'https://www.dell.com', 'Dell workstations, XPS and business computers'),
        ('De\'Longhi', 'delonghi', 'https://www.delonghi.com', 'De\'Longhi premium Italian coffee makers'),
    ]
    brands = {}
    for name, slug, web, desc in brands_data:
        b, _ = Brand.objects.get_or_create(slug=slug, defaults={'name': name, 'website': web, 'description': desc})
        brands[slug] = b

    print("--- 3. Atributlar va Qiymatlarni yaratish ---")
    attr_color, _ = Attribute.objects.get_or_create(slug='color', defaults={'name': 'Color'})
    attr_storage, _ = Attribute.objects.get_or_create(slug='storage', defaults={'name': 'Storage'})
    attr_ram, _ = Attribute.objects.get_or_create(slug='ram', defaults={'name': 'RAM'})
    attr_size, _ = Attribute.objects.get_or_create(slug='size', defaults={'name': 'Size'})

    def get_attr_val(attribute, val):
        s = slugify(f"{attribute.slug}-{val}")
        av, _ = AttributeValue.objects.get_or_create(attribute=attribute, value=val, defaults={'slug': s})
        return av

    # Foydalanuvchilar (sharhlar uchun)
    users = list(User.objects.filter(is_active=True))
    if len(users) < 4:
        u_sardor, _ = User.objects.get_or_create(
            email='sardor.rahimov@example.com',
            defaults={'first_name': 'Sardor', 'last_name': 'Rahimov', 'role': 'customer'}
        )
        u_malika, _ = User.objects.get_or_create(
            email='malika.umarova@example.com',
            defaults={'first_name': 'Malika', 'last_name': 'Umarova', 'role': 'customer'}
        )
        users = list(User.objects.filter(is_active=True))

    print("--- 4. Mahsulotlar to'plamini shakllantirish ---")
    products_catalog = [
        # --- SMARTPHONES ---
        {
            'name': 'Apple iPhone 15 Pro Max',
            'slug': 'iphone-15-pro-max',
            'brand': brands['apple'],
            'primary_category': cat_smartphones,
            'short_description': 'Titan korpus, 5x optik zoom va A17 Pro qudratli chipi.',
            'description': 'iPhone 15 Pro Max — Apple kompaniyasining eng kuchli flagmani. 6.7 dyuymli Super Retina XDR ProMotion ekrani, eng yangi A17 Pro protsessori hamda 48MP periskopli kamera tizimi bilan professional suratga olish imkonini beradi.',
            'image_url': 'https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=800&q=80',
            'variants': [
                {'sku': 'IPH15PM-256-NT', 'title': '256GB Natural Titanium', 'price': '1199.00', 'discount': '1149.00', 'qty': 18, 'is_default': True,
                 'attrs': [(attr_color, 'Natural Titanium'), (attr_storage, '256GB')]},
                {'sku': 'IPH15PM-512-BK', 'title': '512GB Black Titanium', 'price': '1399.00', 'discount': None, 'qty': 10, 'is_default': False,
                 'attrs': [(attr_color, 'Black'), (attr_storage, '512GB')]},
                {'sku': 'IPH15PM-1TB-BL', 'title': '1TB Blue Titanium', 'price': '1599.00', 'discount': None, 'qty': 4, 'is_default': False,
                 'attrs': [(attr_color, 'Blue'), (attr_storage, '1TB')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Eng yaxshi kamera!', 'comment': 'Telefon nihoyatda tez ishlaydi, titan korpus tufayli avvalgilariga qaraganda ancha yengil.', 'pros': 'Kamera, batareya, A17 Pro', 'cons': 'Narxi qimmatroq'},
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Mukammal smartfon', 'comment': 'Batareyasi bemalol 1.5 kunga yetadi, displey 120Hz oqim kabi tekis.', 'pros': 'Displey, Action Button', 'cons': 'Yo\'q'},
            ]
        },
        {
            'name': 'Apple iPhone 15',
            'slug': 'iphone-15',
            'brand': brands['apple'],
            'primary_category': cat_smartphones,
            'short_description': 'Dynamic Island, 48MP asosiy kamera va zamonaviy USB-C porti.',
            'description': 'Yangi iPhone 15 barcha kundalik vazifalar uchun universal tanlov. Rangli mat orqa oyna, Dynamic Island qulay bildirishnomalari va A16 Bionic protsessori.',
            'image_url': 'https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=800&q=80',
            'variants': [
                {'sku': 'IPH15-128-BK', 'title': '128GB Black', 'price': '799.00', 'discount': '749.00', 'qty': 25, 'is_default': True,
                 'attrs': [(attr_color, 'Black'), (attr_storage, '128GB')]},
                {'sku': 'IPH15-256-BL', 'title': '256GB Blue', 'price': '899.00', 'discount': None, 'qty': 15, 'is_default': False,
                 'attrs': [(attr_color, 'Blue'), (attr_storage, '256GB')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Qulay va ixcham', 'comment': 'USB-C nihoyat qo\'shilgani juda yaxshi bo\'ldi, endi hamma qurilmaga bir kabel yetadi.', 'pros': 'USB-C, Dynamic Island', 'cons': '60Hz ekran'},
            ]
        },
        {
            'name': 'Samsung Galaxy Z Fold 5',
            'slug': 'samsung-galaxy-z-fold5',
            'brand': brands['samsung'],
            'primary_category': cat_smartphones,
            'short_description': 'Bukiluvchi ulkan 7.6 dyuymli ekran va multitasking flagmani.',
            'description': 'Samsung Galaxy Z Fold 5 — cho\'ntagingizdagi to\'liq quvvatli planshet. Flex Hinge yangi ilmog\'i orqali tirqishsiz yopiladi, Snapdragon 8 Gen 2 for Galaxy esa eng og\'ir ilovalarni bir vaqtda boshqaradi.',
            'image_url': 'https://images.unsplash.com/photo-1580910051074-3eb694886505?w=800&q=80',
            'variants': [
                {'sku': 'SM-ZFOLD5-256-BK', 'title': '256GB Phantom Black', 'price': '1799.00', 'discount': '1649.00', 'qty': 8, 'is_default': True,
                 'attrs': [(attr_color, 'Black'), (attr_storage, '256GB'), (attr_ram, '16GB')]},
                {'sku': 'SM-ZFOLD5-512-BL', 'title': '512GB Icy Blue', 'price': '1919.00', 'discount': None, 'qty': 5, 'is_default': False,
                 'attrs': [(attr_color, 'Blue'), (attr_storage, '512GB'), (attr_ram, '16GB')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Ish uchun tengsiz', 'comment': 'Bir vaqtning o\'zida 3 ta ilovani ochib ishlash mumkin. Ekran sifati ajoyib.', 'pros': 'Katta ekran, kuchli protsessor', 'cons': 'Og\'irroq'},
            ]
        },
        {
            'name': 'Xiaomi 14 Ultra',
            'slug': 'xiaomi-14-ultra',
            'brand': brands['xiaomi'],
            'primary_category': cat_smartphones,
            'short_description': 'Leica Summilux professional 1-dyuymli 4 kamerali fotoflagman.',
            'description': 'Xiaomi 14 Ultra fotograflar va texnologiya ixlosmandlari uchun yaratilgan. Leica optikasi, o\'zgaruvchan diafragma (f/1.63 - f/4.0), Snapdragon 8 Gen 3 va 90W tezkor zaryadlash.',
            'image_url': 'https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=800&q=80',
            'variants': [
                {'sku': 'MI-14U-512-BK', 'title': '512GB Black / 16GB RAM', 'price': '1299.00', 'discount': '1199.00', 'qty': 12, 'is_default': True,
                 'attrs': [(attr_color, 'Black'), (attr_storage, '512GB'), (attr_ram, '16GB')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Haqiqiy fotoapparat', 'comment': 'Suratlari shunchaki fantastik, ayniqsa tunda va portret rejimida.', 'pros': 'Kamera, tezkor quvvatlanish', 'cons': 'Katta kamera moduli'},
            ]
        },
        {
            'name': 'Google Pixel 8 Pro',
            'slug': 'google-pixel-8-pro',
            'brand': brands['google'],
            'primary_category': cat_smartphones,
            'short_description': 'Google AI kuchiga ega sof Android va ajoyib fototizim.',
            'description': 'Google Tensor G3 chipi, Magic Editor, Best Take va 7 yillik to\'liq Android yangilanish kafolati bilan Google eng kuchli aqlli smartfoni.',
            'image_url': 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800&q=80',
            'variants': [
                {'sku': 'PIX8P-128-OB', 'title': '128GB Obsidian', 'price': '999.00', 'discount': '899.00', 'qty': 14, 'is_default': True,
                 'attrs': [(attr_color, 'Black'), (attr_storage, '128GB')]},
                {'sku': 'PIX8P-256-PC', 'title': '256GB Porcelain', 'price': '1059.00', 'discount': None, 'qty': 8, 'is_default': False,
                 'attrs': [(attr_color, 'White'), (attr_storage, '256GB')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 4, 'title': 'AI imkoniyatlari hayratlanarli', 'comment': 'Fotolarni tahrirlash sun\'iy intellekt orqali juda qulay.', 'pros': 'Kamera, sof interfeys', 'cons': 'Batareya o\'rtacha'},
            ]
        },

        # --- LAPTOPS ---
        {
            'name': 'Apple MacBook Air 15" M3',
            'slug': 'macbook-air-15-m3',
            'brand': brands['apple'],
            'primary_category': cat_laptops,
            'short_description': 'Yupqa alyuminiy korpus, 15.3" Liquid Retina va M3 chipi.',
            'description': 'MacBook Air 15 dyuymli katta ekranga ega bo\'lishiga qaramay juda yengil va nozik. Ventilatorsiz mutlaqo sokin ishlaydi, 18 soatlik avtonom quvvat esa kun bo\'yi zaryadsiz ishlash imkonini beradi.',
            'image_url': 'https://images.unsplash.com/photo-1611186871348-b1ce696e52c9?w=800&q=80',
            'variants': [
                {'sku': 'MBA15-M3-16-512-MD', 'title': '16GB / 512GB Midnight', 'price': '1499.00', 'discount': '1399.00', 'qty': 16, 'is_default': True,
                 'attrs': [(attr_color, 'Midnight'), (attr_ram, '16GB'), (attr_storage, '512GB')]},
                {'sku': 'MBA15-M3-16-256-SG', 'title': '16GB / 256GB Space Gray', 'price': '1299.00', 'discount': None, 'qty': 9, 'is_default': False,
                 'attrs': [(attr_color, 'Space Gray'), (attr_ram, '16GB'), (attr_storage, '256GB')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Mukammal ishchi noutbuk', 'comment': 'Dasturlash va ofis ishlari uchun ideal, batareyasi hech qachon pand bermaydi.', 'pros': 'Sokinlik, katta displey, batareya', 'cons': 'Portlar soni kam'},
            ]
        },
        {
            'name': 'ASUS ROG Zephyrus G16 (2024)',
            'slug': 'asus-rog-zephyrus-g16',
            'brand': brands['asus'],
            'primary_category': cat_laptops,
            'short_description': 'RTX 4080 grafikasi va 2.5K 240Hz OLED ekranli geymerlik qudrati.',
            'description': 'ASUS ROG Zephyrus G16 — zamonaviy o\'yinlar va 3D modellashtirish uchun ultra yengil flagman noutbuk. Intel Core Ultra 9, ROG Nebula OLED ekrani hamda Slash Lighting zamonaviy dizayni.',
            'image_url': 'https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=800&q=80',
            'variants': [
                {'sku': 'ASUS-G16-32-1TB', 'title': '32GB / 1TB RTX 4080 Eclipse Gray', 'price': '2499.00', 'discount': '2299.00', 'qty': 6, 'is_default': True,
                 'attrs': [(attr_color, 'Space Gray'), (attr_ram, '32GB'), (attr_storage, '1TB')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'O\'yinlar uchun monstr', 'comment': 'Cyberpunk 2077 ultra sozlamalarda yugurib ketadi. OLED displey ranglari shunchaki aql bovar qilmas darajada to\'yingan.', 'pros': 'Ekran, unumdorlik', 'cons': 'Yuklama ostida shovqinli'},
            ]
        },
        {
            'name': 'Lenovo ThinkPad X1 Carbon Gen 12',
            'slug': 'lenovo-thinkpad-x1-carbon-gen-12',
            'brand': brands['lenovo'],
            'primary_category': cat_laptops,
            'short_description': 'Biznes etaloni, uglerod tolali engil korpus va 2.8K OLED ekran.',
            'description': 'ThinkPad X1 Carbon — jahon korporativ dunyosining eng ishonchli ultrabuki. 1.09 kg engil og\'irlik, afsonaviy klaviatura, TrackPoint va MIL-SPEC harbiy chidamlilik standarti.',
            'image_url': 'https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=800&q=80',
            'variants': [
                {'sku': 'THINK-X1-32-1TB', 'title': '32GB / 1TB Black', 'price': '1899.00', 'discount': '1749.00', 'qty': 11, 'is_default': True,
                 'attrs': [(attr_color, 'Black'), (attr_ram, '32GB'), (attr_storage, '1TB')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Eng qulay klaviatura', 'comment': 'Matn terish va biznes sayohatlar uchun bundan yaxshiroq noutbuk yo\'q.', 'pros': 'Klaviatura, engillik, xavfsizlik', 'cons': 'Narxi baland'},
            ]
        },
        {
            'name': 'Dell XPS 15 (9530)',
            'slug': 'dell-xps-15',
            'brand': brands['dell'],
            'primary_category': cat_laptops,
            'short_description': 'InfinityEdge 3.5K OLED sensorli ekran va Intel Core i9 quvvati.',
            'description': 'Dell XPS 15 — video montajchilar, grafik dizaynerlar va ijodkorlar uchun mukammal noutbuk. CNC alyuminiy korpus, uglerod tolali kaft tayanchi va yuqori rang aniqligi.',
            'image_url': 'https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=800&q=80',
            'variants': [
                {'sku': 'DELL-XPS15-32-1TB', 'title': '32GB / 1TB Silver', 'price': '2199.00', 'discount': '1999.00', 'qty': 7, 'is_default': True,
                 'attrs': [(attr_color, 'Silver'), (attr_ram, '32GB'), (attr_storage, '1TB')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Dizayn va kuch uyg\'unligi', 'comment': '4K video montajda Premiere Pro juda tez render qiladi.', 'pros': 'Sensorli OLED ekran, ovoz tizimi', 'cons': 'Faqat Type-C portlar'},
            ]
        },

        # --- AUDIO & HEADPHONES ---
        {
            'name': 'Sony WH-1000XM5 Wireless Headphones',
            'slug': 'sony-wh-1000xm5',
            'brand': brands['sony'],
            'primary_category': cat_audio,
            'short_description': 'Sanoatdagi eng ilg\'or faol shovqinni so\'ndirish va 30 soatlik tinglash.',
            'description': 'Sony WH-1000XM5 ikki protsessorli faol shovqin to\'xtatish (ANC) texnologiyasi, LDAC yuqori aniqlikdagi audio kodeki va nafis yumshoq charmli korpusga ega.',
            'image_url': 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&q=80',
            'variants': [
                {'sku': 'SONY-XM5-BK', 'title': 'Black', 'price': '399.00', 'discount': '349.00', 'qty': 20, 'is_default': True,
                 'attrs': [(attr_color, 'Black')]},
                {'sku': 'SONY-XM5-SL', 'title': 'Silver', 'price': '399.00', 'discount': '349.00', 'qty': 12, 'is_default': False,
                 'attrs': [(attr_color, 'Silver')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Shovqindan butkul uzilish', 'comment': 'Samolyotda yoki gavjum ofisda shovqinni nol darajaga tushirib beradi.', 'pros': 'Shovqin bosish, qulaylik', 'cons': 'Buklanmaydigan korpus'},
            ]
        },
        {
            'name': 'Apple AirPods Pro (2nd Gen, USB-C)',
            'slug': 'airpods-pro-2',
            'brand': brands['apple'],
            'primary_category': cat_audio,
            'short_description': 'H2 chipi, 2x kuchliroq shovqin so\'ndirish va USB-C MagSafe g\'ilof.',
            'description': 'AirPods Pro 2 adaptiv audio, ovozni shaxsiylashtirilgan fazoviy eshittirish (Spatial Audio) va kutilmagan suhbatlarda avtomatik ovoz pasaytirish funksiyalariga ega.',
            'image_url': 'https://images.unsplash.com/photo-1600294037681-c80b4cb5b434?w=800&q=80',
            'variants': [
                {'sku': 'APP2-USBC-WH', 'title': 'White MagSafe Case', 'price': '249.00', 'discount': '219.00', 'qty': 30, 'is_default': True,
                 'attrs': [(attr_color, 'White')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Har kungi ajralmas hamroh', 'comment': 'Quloqda juda mahkam va sezilarsiz turadi, baslari nihoyatda tiniq.', 'pros': 'Shovqin bosish, mikrofon, ixchamlik', 'cons': 'Oson chiziladigan keys'},
            ]
        },
        {
            'name': 'Apple AirPods Max',
            'slug': 'airpods-max',
            'brand': brands['apple'],
            'primary_category': cat_audio,
            'short_description': 'Hi-Fi akustika, hisob-kitobli audio va premium zanglamas po\'lat.',
            'description': 'Apple AirPods Max to\'liq o\'lchamli quloqchinlarida dinamik drayverlar har bir tovush nuansini boricha ifodalaydi. Nafas oluvchi to\'rli boshbog\' bosimni teng taqsimlaydi.',
            'image_url': 'https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=800&q=80',
            'variants': [
                {'sku': 'APM-SG', 'title': 'Space Gray', 'price': '549.00', 'discount': '479.00', 'qty': 8, 'is_default': True,
                 'attrs': [(attr_color, 'Space Gray')]},
                {'sku': 'APM-SL', 'title': 'Silver', 'price': '549.00', 'discount': None, 'qty': 5, 'is_default': False,
                 'attrs': [(attr_color, 'Silver')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Premial ovoz sifati', 'comment': 'Film ko\'rishda xuddi kinoteatrdagi kabi effekt beradi.', 'pros': 'Materiallar sifati, Spatial Audio', 'cons': 'Og\'irligi'},
            ]
        },
        {
            'name': 'Samsung Galaxy Buds2 Pro',
            'slug': 'galaxy-buds-2-pro',
            'brand': brands['samsung'],
            'primary_category': cat_audio,
            'short_description': '24-bit Hi-Fi audio, 360 Audio va ergonomik qulay dizayn.',
            'description': 'Samsung Galaxy Buds2 Pro — Galaxy ekotizimidagi eng yaxshi simsiz quloqchin. Shamolga qarshi aerodinamik korpus va tiniq qo\'ng\'iroqlar.',
            'image_url': 'https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=800&q=80',
            'variants': [
                {'sku': 'GBUDS2P-GR', 'title': 'Graphite', 'price': '229.00', 'discount': '179.00', 'qty': 15, 'is_default': True,
                 'attrs': [(attr_color, 'Graphite')]},
                {'sku': 'GBUDS2P-WH', 'title': 'White', 'price': '229.00', 'discount': None, 'qty': 10, 'is_default': False,
                 'attrs': [(attr_color, 'White')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 4, 'title': 'Juda qulay', 'comment': 'Quloqda juda mustahkam o\'tiradi, yugurishda ham tushib ketmaydi.', 'pros': 'Ovoz, ixchamlik', 'cons': 'Batareya 5 soat'},
            ]
        },
        {
            'name': 'JBL Charge 5 Portable Speaker',
            'slug': 'jbl-charge-5',
            'brand': brands['jbl'],
            'primary_category': cat_audio,
            'short_description': 'Kuchli JBL Original Pro baslari, IP67 himoya va 20 soatlik quvvat.',
            'description': 'JBL Charge 5 sayrlar, hovuz bo\'yi va tabiat qo\'ynidagi bazmlar uchun ideal. Alohida tvitter va ikkita passiv radiator kuchli chuqur bas beradi, o\'rnatilgan powerbank esa telefoningizni quvvatlaydi.',
            'image_url': 'https://images.unsplash.com/photo-1545454675-3531b543be5d?w=800&q=80',
            'variants': [
                {'sku': 'JBL-CHG5-BK', 'title': 'Black', 'price': '179.00', 'discount': '149.00', 'qty': 22, 'is_default': True,
                 'attrs': [(attr_color, 'Black')]},
                {'sku': 'JBL-CHG5-BL', 'title': 'Blue', 'price': '179.00', 'discount': '149.00', 'qty': 14, 'is_default': False,
                 'attrs': [(attr_color, 'Blue')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Baslari aqlbovar qilmas', 'comment': 'Ochiq havoda ham ovozi juda baland va tiniq yangraydi.', 'pros': 'Bas, batareya, suv o\'tkazmaslik', 'cons': 'Mikrofoni yo\'q'},
            ]
        },
        {
            'name': 'Marshall Emberton II',
            'slug': 'marshall-emberton-2',
            'brand': brands['marshall'],
            'primary_category': cat_audio,
            'short_description': '360° True Stereophonic tovush va 30+ soatlik avtonom quvvat.',
            'description': 'Marshall Emberton II o\'ziga xos vintage rok-n-roll dizayni, silikon mustahkam korpusi va 360 darajali keng fazoviy ovoz tarqatish qobiliyati bilan ajralib turadi.',
            'image_url': 'https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=800&q=80',
            'variants': [
                {'sku': 'MAR-EMB2-BB', 'title': 'Black and Brass', 'price': '169.00', 'discount': None, 'qty': 9, 'is_default': True,
                 'attrs': [(attr_color, 'Black')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Dizayn va musiqiy lazzat', 'comment': 'Stol ustida ajoyib ko\'rinadi, rok va klassik musiqalarni ajoyib ijro etadi.', 'pros': 'Dizayn, toza vokal', 'cons': 'Dasturi oddiy'},
            ]
        },

        # --- SMART WATCHES & WEARABLES ---
        {
            'name': 'Apple Watch Ultra 2',
            'slug': 'apple-watch-ultra-2',
            'brand': brands['apple'],
            'primary_category': cat_wearables,
            'short_description': '49mm titan korpus, 3000 nitli eng yorqin ekran va S9 SiP chipi.',
            'description': 'Ekstremal sportchilar, sayyohlar va faol hayot tarzi egalari uchun yaratilgan. Ikki chastotali aniq GPS, sho\'ng\'ish kompyuteri va 72 soatlik kam quvvat rejimi.',
            'image_url': 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&q=80',
            'variants': [
                {'sku': 'AW-ULT2-OR', 'title': '49mm Titanium / Orange Ocean Band', 'price': '799.00', 'discount': '749.00', 'qty': 11, 'is_default': True,
                 'attrs': [(attr_color, 'Natural Titanium')]},
                {'sku': 'AW-ULT2-BL', 'title': '49mm Titanium / Blue Trail Loop', 'price': '799.00', 'discount': None, 'qty': 8, 'is_default': False,
                 'attrs': [(attr_color, 'Natural Titanium')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Eng chidamli soat', 'comment': 'Tog\'larda navigatsiya va sport bilan shug\'ullanishda tengi yo\'q.', 'pros': 'Ekran yorqinligi, titan mustahkamligi', 'cons': 'Katta o\'lcham'},
            ]
        },
        {
            'name': 'Apple Watch Series 9',
            'slug': 'apple-watch-series-9',
            'brand': brands['apple'],
            'primary_category': cat_wearables,
            'short_description': 'Double Tap jest boshqaruvi, S9 protsessor va doimiy salomatlik nazorati.',
            'description': 'Apple Watch Series 9 kunlik salomatlik, EKG, qondagi kislorod miqdori va jismoniy faollikni kuzatishda eng yaxshi yordamchingiz.',
            'image_url': 'https://images.unsplash.com/photo-1510017803434-a899398421b3?w=800&q=80',
            'variants': [
                {'sku': 'AWS9-45-MD', 'title': '45mm Midnight Aluminum', 'price': '429.00', 'discount': '389.00', 'qty': 17, 'is_default': True,
                 'attrs': [(attr_color, 'Midnight')]},
                {'sku': 'AWS9-41-SL', 'title': '41mm Silver Aluminum', 'price': '399.00', 'discount': None, 'qty': 13, 'is_default': False,
                 'attrs': [(attr_color, 'Silver')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Double tap ajoyib', 'comment': 'Qo\'lingiz band bo\'lsa ham barmoqlarni ikki marta tekkizib qo\'ng\'iroqqa javob berish juda qulay.', 'pros': 'Double Tap, tezkorlik', 'cons': 'Har kuni quvvatlash kerak'},
            ]
        },
        {
            'name': 'Samsung Galaxy Watch 6 Classic',
            'slug': 'galaxy-watch-6-classic',
            'brand': brands['samsung'],
            'primary_category': cat_wearables,
            'short_description': 'Aylanuvchi mexanik bezel, safir shisha va uyqu murabbiyligi.',
            'description': 'Galaxy Watch 6 Classic an\'anaviy hashamatli soat ko\'rinishini ilg\'or aqlli funksiyalar bilan birlashtiradi. Zanglamas po\'lat, tana tarkibi tahlili va yurak ritmi monitoringi.',
            'image_url': 'https://images.unsplash.com/photo-1579586337278-3befd40fd17a?w=800&q=80',
            'variants': [
                {'sku': 'GW6C-47-BK', 'title': '47mm Black Stainless Steel', 'price': '429.00', 'discount': '369.00', 'qty': 14, 'is_default': True,
                 'attrs': [(attr_color, 'Black')]},
                {'sku': 'GW6C-43-SL', 'title': '43mm Silver Stainless Steel', 'price': '399.00', 'discount': None, 'qty': 9, 'is_default': False,
                 'attrs': [(attr_color, 'Silver')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Klassik va juda qulay', 'comment': 'Aylanuvchi bezeli orqali menyuni boshqarish sensorli ekranga qaraganda ancha yoqimli.', 'pros': 'Mexanik bezel, safir shisha', 'cons': 'Batareya 1-2 kun'},
            ]
        },
        {
            'name': 'Xiaomi Smart Band 8 Pro',
            'slug': 'xiaomi-smart-band-8-pro',
            'brand': brands['xiaomi'],
            'primary_category': cat_wearables,
            'short_description': 'Katta 1.74" AMOLED ekran, GNSS GPS va 14 kunlik batareya.',
            'description': 'Smart Band 8 Pro katta to\'rtburchak displey, mustaqil yo\'ldosh navigatsiyasi va 150 dan ortiq sport rejimlari bilan arzon va qulay bilaguzuk.',
            'image_url': 'https://images.unsplash.com/photo-1575311373937-040b8e1fd5b6?w=800&q=80',
            'variants': [
                {'sku': 'MI-BAND8P-BK', 'title': 'Black TPU Strap', 'price': '79.00', 'discount': '65.00', 'qty': 40, 'is_default': True,
                 'attrs': [(attr_color, 'Black')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Narxiga nisbatan ajoyib', 'comment': 'Batareyasi deyarli 2 hafta bemalol yetadi, bildirishnomalar katta ekranda yaxshi o\'qiladi.', 'pros': 'Batareya, narx, ekran', 'cons': 'NFC hamma joyda ishlamaydi'},
            ]
        },

        # --- TABLETS ---
        {
            'name': 'Apple iPad Pro 13" M4',
            'slug': 'ipad-pro-13-m4',
            'brand': brands['apple'],
            'primary_category': cat_tablets,
            'short_description': 'Ultra Retina XDR Tandem OLED ekrani, M4 chipi va faqat 5.1mm qalinlik.',
            'description': 'Yangi iPad Pro dunyodagi eng ilg\'or Ultra Retina XDR ikki qatlamli OLED displeyi va Apple M4 chipi bilan qurollangan. Ilhomlantiruvchi ijod va professional ish stansiyasi.',
            'image_url': 'https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=800&q=80',
            'variants': [
                {'sku': 'IPADP13-M4-256-BK', 'title': '256GB Space Black', 'price': '1299.00', 'discount': None, 'qty': 12, 'is_default': True,
                 'attrs': [(attr_color, 'Space Gray'), (attr_storage, '256GB')]},
                {'sku': 'IPADP13-M4-512-SL', 'title': '512GB Silver', 'price': '1499.00', 'discount': None, 'qty': 7, 'is_default': False,
                 'attrs': [(attr_color, 'Silver'), (attr_storage, '512GB')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'OLED displey shunchaki mo\'jiza', 'comment': 'Ranglar chuqurligi, yupqaligi va M4 tezligi hayratga soladi.', 'pros': 'Ekran, noziklik, tezlik', 'cons': 'iPadOS cheklovlari'},
            ]
        },
        {
            'name': 'Samsung Galaxy Tab S9 Ultra',
            'slug': 'galaxy-tab-s9-ultra',
            'brand': brands['samsung'],
            'primary_category': cat_tablets,
            'short_description': 'Ulkan 14.6" Dynamic AMOLED 2X ekran, IP68 suvdan himoya va S Pen.',
            'description': 'Galaxy Tab S9 Ultra ulkan ekran, o\'rnatilgan qulay S Pen elektron qalami, Dex kompyuter rejimi hamda suv va changdan to\'liq IP68 himoyaga ega.',
            'image_url': 'https://images.unsplash.com/photo-1561154464-82e9adf32764?w=800&q=80',
            'variants': [
                {'sku': 'GTAB-S9U-256-GR', 'title': '256GB Graphite / S-Pen Included', 'price': '1199.00', 'discount': '1049.00', 'qty': 8, 'is_default': True,
                 'attrs': [(attr_color, 'Graphite'), (attr_storage, '256GB')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Rasm chizish va kino ko\'rish uchun 1-raqam', 'comment': 'S Pen qalami bepul qutidan chiqishi juda yoqimli. Ekran esa televizordek katta.', 'pros': 'Ulkan AMOLED ekran, S-Pen', 'cons': 'Kattaligi sababli bir qo\'lda ushlash qiyin'},
            ]
        },

        # --- GAMING ---
        {
            'name': 'Sony PlayStation 5 Slim',
            'slug': 'playstation-5-slim',
            'brand': brands['sony'],
            'primary_category': cat_gaming,
            'short_description': 'Tezkor SSD, 4K 120Hz o\'yinlar va DualSense innovatsion kontrolleri.',
            'description': 'PlayStation 5 Slim 1TB o\'rnatilgan SSD xotira, yangilangan ixcham korpus va immersiv haptic taktil qaytarish bilan eng zamonaviy o\'yin tajribasini taqdim etadi.',
            'image_url': 'https://images.unsplash.com/photo-1606813907291-d86efa9b94db?w=800&q=80',
            'variants': [
                {'sku': 'PS5-SLIM-DISC', 'title': '1TB Disc Edition White', 'price': '499.00', 'discount': None, 'qty': 15, 'is_default': True,
                 'attrs': [(attr_color, 'White'), (attr_storage, '1TB')]},
                {'sku': 'PS5-SLIM-DIG', 'title': '1TB Digital Edition White', 'price': '449.00', 'discount': None, 'qty': 10, 'is_default': False,
                 'attrs': [(attr_color, 'White'), (attr_storage, '1TB')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'O\'yin olamidagi cho\'qqi', 'comment': 'Yuklanish vaqti soniyalar ichida sodir bo\'ladi, DualSense triggerlari hissi ajoyib.', 'pros': 'Tezlik, DualSense, eksklyuziv o\'yinlar', 'cons': 'Aksessuarlar narxi'},
            ]
        },

        # --- FOOTWEAR ---
        {
            'name': 'Nike Air Force 1 \'07',
            'slug': 'nike-air-force-1',
            'brand': brands['nike'],
            'primary_category': cat_footwear,
            'short_description': 'Afsonaviy shahar krossovkasi, qalin charm ustki qism va Nike Air qulayligi.',
            'description': 'Nike Air Force 1 \'07 — barcha zamonlarning eng ommabop krossovkasi. Chidamli tikilgan charm qoplamalar, toza oq rang va qulay amortizatsiya.',
            'image_url': 'https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=800&q=80',
            'variants': [
                {'sku': 'AF1-WH-41', 'title': 'Triple White / Size 41', 'price': '115.00', 'discount': None, 'qty': 15, 'is_default': False,
                 'attrs': [(attr_color, 'White'), (attr_size, '41')]},
                {'sku': 'AF1-WH-42', 'title': 'Triple White / Size 42', 'price': '115.00', 'discount': None, 'qty': 20, 'is_default': True,
                 'attrs': [(attr_color, 'White'), (attr_size, '42')]},
                {'sku': 'AF1-WH-43', 'title': 'Triple White / Size 43', 'price': '115.00', 'discount': None, 'qty': 18, 'is_default': False,
                 'attrs': [(attr_color, 'White'), (attr_size, '43')]},
                {'sku': 'AF1-BK-42', 'title': 'Triple Black / Size 42', 'price': '115.00', 'discount': None, 'qty': 12, 'is_default': False,
                 'attrs': [(attr_color, 'Black'), (attr_size, '42')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Universal uslub', 'comment': 'Har qanday kiyim bilan mos tushadi, juda mustahkam.', 'pros': 'Dizayn, chidamlilik', 'cons': 'Oq rang tez kirlanadi'},
            ]
        },
        {
            'name': 'Adidas Samba OG',
            'slug': 'adidas-samba-og',
            'brand': brands['adidas'],
            'primary_category': cat_footwear,
            'short_description': 'Afsonaviy retro krossovka, tabiiy charm va zamsh qoplama.',
            'description': '1950-yillardan buyon o\'z jozibasini yo\'qotmagan afsona. Gum rezina taglik, T shaklidagi zamsh burun qismi va kontrast 3 tasma.',
            'image_url': 'https://images.unsplash.com/photo-1518002171953-a080ee817e1f?w=800&q=80',
            'variants': [
                {'sku': 'SAMBA-WH-41', 'title': 'Cloud White / Core Black Size 41', 'price': '100.00', 'discount': None, 'qty': 10, 'is_default': False,
                 'attrs': [(attr_color, 'White'), (attr_size, '41')]},
                {'sku': 'SAMBA-WH-42', 'title': 'Cloud White / Core Black Size 42', 'price': '100.00', 'discount': None, 'qty': 16, 'is_default': True,
                 'attrs': [(attr_color, 'White'), (attr_size, '42')]},
                {'sku': 'SAMBA-BK-43', 'title': 'Core Black / Size 43', 'price': '100.00', 'discount': None, 'qty': 8, 'is_default': False,
                 'attrs': [(attr_color, 'Black'), (attr_size, '43')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Trenddagi poyabzal', 'comment': 'Jinsi va shimlar bilan ajoyib yarashadi, oyoqda engil turadi.', 'pros': 'Retro uslub, sifatli charm', 'cons': 'Yupqa taglik'},
            ]
        },
        {
            'name': 'Adidas Ultraboost Light',
            'slug': 'adidas-ultraboost-light',
            'brand': brands['adidas'],
            'primary_category': cat_footwear,
            'short_description': 'Eng engil Light BOOST materiali, cheksiz energiya qaytarish.',
            'description': 'Ultraboost Light avvalgi avlodlarga qaraganda 30% engilroq BOOST materialiga ega. Continental rezina taglik har qanday havoda ishonchli ushlaydi.',
            'image_url': 'https://images.unsplash.com/photo-1587563871167-1ee9c731aefb?w=800&q=80',
            'variants': [
                {'sku': 'UB-LT-BK-42', 'title': 'Core Black / Size 42', 'price': '190.00', 'discount': '155.00', 'qty': 14, 'is_default': True,
                 'attrs': [(attr_color, 'Black'), (attr_size, '42')]},
                {'sku': 'UB-LT-BK-43', 'title': 'Core Black / Size 43', 'price': '190.00', 'discount': '155.00', 'qty': 11, 'is_default': False,
                 'attrs': [(attr_color, 'Black'), (attr_size, '43')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Yugurish uchun tengsiz', 'comment': 'Amortizatsiyasi bulut ustida yurgandek his beradi. Oyoq umuman charchamaydi.', 'pros': 'Qulaylik, amortizatsiya', 'cons': 'Narxi balandroq'},
            ]
        },
        {
            'name': 'Puma RS-X Reinvention',
            'slug': 'puma-rs-x',
            'brand': brands['puma'],
            'primary_category': cat_footwear,
            'short_description': 'Massiv retro siluet va Running System qulay amortizatsiyasi.',
            'description': 'Puma RS-X o\'zgacha zamonaviy retro estetika va qulay Running System texnologiyasiga ega yorqin krossovka.',
            'image_url': 'https://images.unsplash.com/photo-1539185441755-769473a23570?w=800&q=80',
            'variants': [
                {'sku': 'PUMA-RSX-42', 'title': 'White / Blue / Size 42', 'price': '120.00', 'discount': '89.00', 'qty': 9, 'is_default': True,
                 'attrs': [(attr_color, 'White'), (attr_size, '42')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 4, 'title': 'Juda chiroyli dizayn', 'comment': 'Yorqin ranglari bilan ko\'chada darhol e\'tibor tortadi.', 'pros': 'Dizayn, narx', 'cons': 'Kengroq bichim'},
            ]
        },

        # --- CLOTHING ---
        {
            'name': 'Nike Sportswear Club Fleece Hoodie',
            'slug': 'nike-club-fleece-hoodie',
            'brand': brands['nike'],
            'primary_category': cat_clothing,
            'short_description': 'Klassik paxtali xudi, yumshoq ichki fleece va qulay bichim.',
            'description': 'Nike Sportswear Club Fleece xudisi sovuq kunlarda issiq va qulay saqlaydi. Ko\'krakdagi kashta Nike logotipi va qulay keng cho\'ntak.',
            'image_url': 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800&q=80',
            'variants': [
                {'sku': 'NK-HOOD-BK-M', 'title': 'Black / Size M', 'price': '65.00', 'discount': None, 'qty': 20, 'is_default': False,
                 'attrs': [(attr_color, 'Black'), (attr_size, 'M')]},
                {'sku': 'NK-HOOD-BK-L', 'title': 'Black / Size L', 'price': '65.00', 'discount': None, 'qty': 25, 'is_default': True,
                 'attrs': [(attr_color, 'Black'), (attr_size, 'L')]},
                {'sku': 'NK-HOOD-GR-L', 'title': 'Grey / Size L', 'price': '65.00', 'discount': None, 'qty': 15, 'is_default': False,
                 'attrs': [(attr_color, 'Silver'), (attr_size, 'L')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Sifatli mato', 'comment': 'Yuvilgandan keyin ham rangi o\'chmaydi, ichki qismi yumshoq.', 'pros': 'Sifat, qulaylik', 'cons': 'Yo\'q'},
            ]
        },
        {
            'name': 'Adidas Essentials 3-Stripes Tracksuit',
            'slug': 'adidas-tracksuit',
            'brand': brands['adidas'],
            'primary_category': cat_clothing,
            'short_description': 'Klassik 3 tasma chiziqli sport kostyumi, zamokli jaket va shim.',
            'description': 'Sport bilan shug\'ullanish va dam olish kunlari uchun afsonaviy Adidas sport libosi. Qulay elastik kamar va nafas oluvchi material.',
            'image_url': 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800&q=80',
            'variants': [
                {'sku': 'AD-TRK-NV-M', 'title': 'Navy Blue / Size M', 'price': '85.00', 'discount': '69.00', 'qty': 18, 'is_default': False,
                 'attrs': [(attr_color, 'Blue'), (attr_size, 'M')]},
                {'sku': 'AD-TRK-NV-L', 'title': 'Navy Blue / Size L', 'price': '85.00', 'discount': '69.00', 'qty': 22, 'is_default': True,
                 'attrs': [(attr_color, 'Blue'), (attr_size, 'L')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Ajoyib kostyum', 'comment': 'Materiali yengil, harakatlanishga hech xalal bermaydi.', 'pros': 'Klassik ko\'rinish, narx', 'cons': 'Yo\'q'},
            ]
        },

        # --- HOME & LIVING ---
        {
            'name': 'Dyson V15 Detect Absolute',
            'slug': 'dyson-v15-detect',
            'brand': brands['dyson'],
            'primary_category': cat_cleaning,
            'short_description': 'Yashirin changni ko\'rsatuvchi lazer nuri va 240 AW kuchli tortish.',
            'description': 'Dyson V15 Detect chang zarralarini hisoblovchi pyezo datchik va chang miqdoriga qarab tortish kuchini avtomatik sozlovchi intellektual changyutgich.',
            'image_url': 'https://images.unsplash.com/photo-1558317374-067fb5f30001?w=800&q=80',
            'variants': [
                {'sku': 'DYSON-V15-ABS', 'title': 'Yellow / Nickel Absolute', 'price': '749.00', 'discount': '649.00', 'qty': 10, 'is_default': True,
                 'attrs': [(attr_color, 'Yellow')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Tozalikning yangi bosqichi', 'comment': 'Lazer nuri gilam va poldagi ko\'rinmas changlarni ko\'rsatganda hayratda qoldim.', 'pros': 'Tortish kuchi, lazer, noziklik', 'cons': 'Narxi qimmat'},
            ]
        },
        {
            'name': 'Xiaomi Robot Vacuum X10+',
            'slug': 'xiaomi-robot-vacuum-x10',
            'brand': brands['xiaomi'],
            'primary_category': cat_cleaning,
            'short_description': 'O\'z-o\'zini tozalash va yuvish stansiyali avtonom robot changyutgich.',
            'description': 'Xiaomi Robot Vacuum X10+ polni changdan tozalaydi, latasini o\'zi yuvadi va issiq havo bilan quritadi. S-Cross AI 3D to\'siqlarni aylanib o\'tish tizimi.',
            'image_url': 'https://images.unsplash.com/photo-1616401784845-180882ba9ba8?w=800&q=80',
            'variants': [
                {'sku': 'MI-X10P-WH', 'title': 'White Smart Station', 'price': '699.00', 'discount': '579.00', 'qty': 8, 'is_default': True,
                 'attrs': [(attr_color, 'White')]},
            ],
            'reviews': [
                {'user': users[0], 'rating': 5, 'title': 'Haqiqiy ozodlik', 'comment': '1 oy davomida umuman qo\'l tekkizmadim, o\'zi tozalab, stansiyaga axlatini to\'kib qo\'yadi.', 'pros': 'To\'liq avtomatizatsiya, quritish', 'cons': 'Katta stansiya'},
            ]
        },
        {
            'name': 'De\'Longhi Magnifica S Smart Coffee Machine',
            'slug': 'delonghi-magnifica-s',
            'brand': brands['delonghi'],
            'primary_category': cat_kitchen,
            'short_description': 'Donador qahvadan yangi espresso va kapuchino tayyorlovchi avtomat.',
            'description': 'De\'Longhi Magnifica S yangi yanchilgan donalardan Italiya sifatidagi espresso va mayin kremli kapuchino tayyorlaydi. 13 darajali po\'lat tegirmon.',
            'image_url': 'https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=800&q=80',
            'variants': [
                {'sku': 'DEL-MAG-S', 'title': 'Silver / Black', 'price': '599.00', 'discount': '499.00', 'qty': 12, 'is_default': True,
                 'attrs': [(attr_color, 'Silver')]},
            ],
            'reviews': [
                {'user': users[1] if len(users) > 1 else users[0], 'rating': 5, 'title': 'Har tong xushbo\'y qahva', 'comment': 'Kofeshopdagi kabi ajoyib kapuchino qiladi. Tozalash va ishlatish juda oson.', 'pros': 'Qahva sifati, po\'lat tegirmon', 'cons': 'Bir oz shovqinli yanchadi'},
            ]
        },
    ]

    for pdata in products_catalog:
        prod, created = Product.objects.get_or_create(
            slug=pdata['slug'],
            defaults={
                'name': pdata['name'],
                'brand': pdata['brand'],
                'short_description': pdata['short_description'],
                'description': pdata['description'],
                'is_active': True,
            }
        )
        if not created:
            prod.name = pdata['name']
            prod.brand = pdata['brand']
            prod.short_description = pdata['short_description']
            prod.description = pdata['description']
            prod.is_active = True
            prod.save()

        # Category mapping
        ProductCategory.objects.get_or_create(
            product=prod,
            category=pdata['primary_category'],
            defaults={'is_primary': True}
        )

        # Rasm yuklash va ProductMedia
        img_filename = f"{pdata['slug']}.jpg"
        media_path = download_image(pdata['image_url'], img_filename)
        ProductMedia.objects.get_or_create(
            product=prod,
            file=media_path,
            defaults={
                'alt_text': pdata['name'],
                'media_type': ProductMedia.MediaType.IMAGE,
                'is_main': True,
                'order': 1,
            }
        )

        # Variantlar
        for vdata in pdata['variants']:
            variant, v_created = ProductVariant.objects.get_or_create(
                sku=vdata['sku'],
                defaults={
                    'product': prod,
                    'title': vdata['title'],
                    'price': Decimal(vdata['price']),
                    'discount_price': Decimal(vdata['discount']) if vdata['discount'] else None,
                    'is_default': vdata['is_default'],
                    'is_active': True,
                }
            )
            if not v_created:
                variant.product = prod
                variant.title = vdata['title']
                variant.price = Decimal(vdata['price'])
                variant.discount_price = Decimal(vdata['discount']) if vdata['discount'] else None
                variant.is_default = vdata['is_default']
                variant.is_active = True
                variant.save()

            # Atribut qiymatlarini ulash
            for attr, val in vdata.get('attrs', []):
                av = get_attr_val(attr, val)
                ProductVariantAttributeValue.objects.get_or_create(variant=variant, attribute_value=av)

            # Inventory
            Inventory.objects.get_or_create(
                variant=variant,
                defaults={
                    'quantity': vdata['qty'],
                    'reserved_quantity': 0,
                    'low_stock_threshold': 5,
                }
            )

        # Sharhlar
        for rdata in pdata.get('reviews', []):
            Review.objects.get_or_create(
                user=rdata['user'],
                product=prod,
                defaults={
                    'rating': rdata['rating'],
                    'title': rdata['title'],
                    'comment': rdata['comment'],
                    'pros': rdata.get('pros', ''),
                    'cons': rdata.get('cons', ''),
                    'status': ReviewStatus.APPROVED,
                    'is_verified_purchase': True,
                    'likes_count': 5,
                    'dislikes_count': 0,
                }
            )

        # Rating summary yangilash
        rating_summary, _ = ProductRatingSummary.objects.get_or_create(product=prod)
        rating_summary.recalculate()

    print(f"Barcha {len(products_catalog)} ta yangi mahsulot muvaffaqiyatli qo'shildi!")

if __name__ == '__main__':
    seed()
