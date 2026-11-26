# Yakıt tüketimini etkileyen değişkenler

Bu not, LTFM–LTFJ yörünge verisinde yakıt tüketimini anlamlı şekilde etkileyen girdi
değişkenlerini ve neden seçildiklerini açıklar. Yakıt OpenAP ile hesaplanır; uçak tipi
icao24 üzerinden eşlenir.

## 1. Veride ne var, ne eksik

Örnek dosya (`LTFM_LTFJ_Haziran2026_Yorunge_Verisi.xlsx`) incelendi:

| Özellik | Değer |
|---|---|
| Satır | 999.999 (tam 1 milyonda kesilmiş, günün tamamı olmayabilir) |
| Tarih | Yalnızca 1 Haziran 2026 (00:00–23:59 UTC) |
| Sütunlar | callsign, time, lat, lon, baroaltitude, velocity, heading |
| Alan | lat 40,5–41,5 / lon 28,0–29,8, irtifa ≤ 10.000 m (terminal sahası kutusu) |
| Örnekleme | 1 saniye |
| Uçuş | 1.371 callsign → ~1.385 uçuş (419 iniş, 493 kalkış, 464 transit/kısmi) |
| Sorunlu kayıt | 15.620 boş callsign, 844 boş hız/yön, 391 ondalık kaymalı değer (ör. lat=40875) |

**Kritik eksik: `icao24` sütunu örnek dosyada yok.** Plan icao24 → uçak tipi olduğu için
1 aylık veri çekilirken şu sütunlar mutlaka eklenmeli (OpenSky `state_vectors_data4`):
`icao24, vertrate, geoaltitude, onground`. Ayrıca 1 aylık veri Excel'e sığmaz (en fazla
~1,05 milyon satır); CSV/CSV.GZ veya parquet olarak alınmalı.

## 2. OpenAP'in doğrudan girdileri (fiziksel belirleyiciler)

`FuelFlow(tip).enroute(mass, tas, alt, vs, acc)` yakıt akışını bu değişkenlerden hesaplar.
Bu yüzden bunlar yakıtı tanım gereği belirler:

| Değişken | Kaynak | Not |
|---|---|---|
| **Uçak tipi / motor** | icao24 → typecode (OpenSky aircraft DB) | Uçuşlar arası farkın en büyük kaynağı. A321 ile B77W arasında yakıt akışı 3–4 kat fark eder. |
| **Kütle (mass)** | Veride yok → MTOW × oran varsayımı | Kalkışta ~%85, inişte ~%70 MTOW varsayıldı. Duyarlılık analizi yapılmalı. |
| **Gerçek hava hızı (TAS)** | `velocity` yer hızıdır | Rüzgar verisi yoksa TAS ≈ yer hızı. ERA5 rüzgarı ile düzeltilebilir. |
| **İrtifa** | `baroaltitude` | Alçakta hava yoğun, sürükleme ve yakıt akışı yüksek. |
| **Dikey hız (vs)** | `vertrate` yoksa irtifa farkından türetilir | Tırmanış yakıtı belirgin artırır. |
| **İvme (acc)** | Hız farkından türetilir | Hızlanma fazlarında itki artar. |

Dikkat: Bu değişkenleri hedef (OpenAP yakıtı) ile birlikte bir modele koymak döngüsel olur,
çünkü yakıt zaten bunlardan hesaplanıyor. Veri madenciliği kısmında önerim, hedefi **uçuş
başına toplam yakıt** (veya referansa göre fazla yakıt) alıp aşağıdaki **operasyonel**
değişkenlerin etkisini ölçmek.

## 3. Veri madenciliği için önerilen girdi değişkenleri (uçuş bazında)

Hepsi `src/yakit/features.py` içinde hesaplanıyor.

| Grup | Değişken | Gerekçe |
|---|---|---|
| Uçak | `typecode`, `ac_mtow`, `ac_engine`, `n_engines` | Ağırlık ve motor verimliliği yakıtın ana belirleyicisi. |
| Operasyon | `operation` (kalkış/iniş), `airport` (LTFM/LTFJ) | Kalkışta tam itkiyle tırmanış, inişte rölantiye yakın alçalma. Örnekte medyan iniş yakıtı LTFM 511 kg, LTFJ 383 kg. |
| Süre/mesafe | `duration_min`, `track_km` | Alanda kalınan süre arttıkça yakıt doğrusal artar. |
| Rota verimsizliği | `path_ratio` (kat edilen / düz mesafe), `turn_total_deg` | Holding ve radar vektörlemesi. İnişte yakıtla en güçlü ilişkili operasyonel değişkenler. |
| Dikey profil | `level_share`, `level_low_min` (3000 m altı yatay uçuş süresi), `vs_mean_abs_ms` | Kademeli alçalma (level-off) sürekli alçalmaya (CDO) göre daha fazla yakıt yakar. |
| Hız profili | `spd_mean_ms`, `spd_std_ms`, `acc_abs_mean` | Hızlanma/yavaşlama sayısı itki değişimini gösterir. |
| İrtifa | `alt_mean_m`, `alt_change_m` | Kalkışta alanda ne kadar tırmanıldığı yakıtı belirler. |
| Zaman/trafik | `hour_local`, `weekday`, `traffic_15min` | Yoğun saatlerde bekleme ve vektörleme artar (1 aylık veride anlam kazanır). |
| Havayolu | `airline` (callsign ilk 3 harf) | Filo ve işletim prosedürü farkı (THY, PGT, AJet ağırlıklı). |
| Hava durumu (opsiyonel) | rüzgar, sıcaklık (ERA5 / METAR) | Karşı rüzgar süreyi uzatır, sıcaklık itkiyi etkiler. |

## 4. Örnek veriyle ilk bulgu

icao24 olmadığı için tüm uçuşlara deneme amaçlı **A320** atanarak OpenAP yakıtı
hesaplandı (912 iniş/kalkış uçuşu). Uçuş başına toplam yakıt ile Spearman korelasyonları:

| Değişken | İniş (n=419) | Kalkış (n=493) |
|---|---|---|
| duration_min | 0,86 | 0,98 |
| track_km | 0,78 | 0,98 |
| turn_total_deg | 0,74 | 0,32 |
| path_ratio | 0,71 | 0,22 |
| level_low_min | 0,66 | 0,13 |
| alt_mean_m | 0,52 | 0,93 |
| spd_mean_ms | 0,50 | 0,85 |
| alt_change_m | −0,51 | 0,96 |
| hour_local | 0,25 | 0,00 |
| traffic_15min | −0,04 | 0,17 |

Yorum:
- **İnişte** yakıtı sürükleyen şey rota verimsizliği: dönüş miktarı, rota uzaması ve
  alçakta yatay uçuş süresi. Bunlar holding ve vektörlemeyle ilgili ve projenin asıl
  analiz edilebilir konusu.
- **Kalkışta** yakıt neredeyse tamamen uçağın kutudan çıkana kadar ne kadar tırmandığına
  ve süreye bağlı. Bunun sebebi verinin 10.000 m ve coğrafi kutuyla kesilmiş olması.
  Karşılaştırılabilir olması için kalkışlarda sabit bir kapıya kadar (ör. pistten
  3.000 m'ye ya da FL100'e) yakıt hesaplanması önerilir.
- Tek tip atandığı için **uçak tipi ve kütlenin etkisi bu tabloda görünmüyor**; gerçek
  tiplerle bu iki değişkenin en güçlü belirleyici çıkması beklenir.

## 5. Önerilen modelleme

1. Hedef: `fuel_kg` (uçuş başına) veya `fuel_per_min`; iniş ve kalkış ayrı modellenir.
2. Modeller: Lineer/Lasso regresyon (yorumlanabilirlik), Random Forest, XGBoost.
3. Değişken önemi: permütasyon önemi ve SHAP; Lasso katsayıları ile karşılaştırma.
4. İstatistiksel test: LTFM/LTFJ ve saat dilimleri arası farklar için Kruskal–Wallis.
5. Streamlit arayüzü: uçuş seçip yörünge ve yakıt profilini gösterme (`app/`).
