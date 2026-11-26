# ISL533 – LTFM/LTFJ Terminal Sahasında Yakıt Tüketimi

İTÜ ISL533 Veri Madenciliği dönem projesi (teslim: 30.12.2026).

İstanbul Havalimanı (LTFM) ve Sabiha Gökçen (LTFJ) çevresindeki ADS-B yörünge
verisinden uçuş bazında yakıt tüketimini OpenAP ile hesaplıyor, yakıtı etkileyen
operasyonel değişkenleri makine öğrenmesi ile analiz ediyoruz.

Değişkenlerin listesi ve gerekçeleri: [docs/degiskenler.md](docs/degiskenler.md)

## Kurulum

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Veri

Veri dosyaları repoya konmaz (`data/` git dışında). Klasöre şu şekilde yerleştirin:

```
data/raw/      ham yörünge verisi (csv, csv.gz, parquet veya xlsx)
data/raw/aircraft_db.csv   OpenSky aircraft database (icao24 → typecode)
data/interim/  güne bölünmüş parquet (otomatik oluşur)
data/processed/flights.parquet  uçuş bazında özellikler + yakıt (çıktı)
```

1 aylık veri için gereken sütunlar: `icao24, callsign, time, lat, lon, baroaltitude,
velocity, heading, vertrate` (varsa `geoaltitude, onground`). 1 aylık veri Excel'e
sığmaz; CSV.GZ veya parquet kullanın.

## Çalıştırma

```bash
python scripts/run_pipeline.py --raw data/raw/haziran2026.csv.gz \
    --aircraft-db data/raw/aircraft_db.csv
```

icao24 olmayan örnek veride deneme için: `--default-type A320`.

Hat her günü ayrı işlediği için bellek kullanımı gün başına sınırlı kalır. Örnek gün
(1 milyon satır) yaklaşık 1 dakikada işleniyor; 1 ay için ~30 dakika beklenir.

## Yapı

```
src/yakit/
  io.py        ham veri okuma, güne göre parquet'e bölme
  clean.py     ondalık kayması düzeltme, eksik/tekrarlı kayıtlar
  segment.py   uçuşlara bölme, kalkış/iniş ve havalimanı sınıflandırma
  aircraft.py  icao24 → uçak tipi → OpenAP tipi
  fuel.py      OpenAP yakıt akışı (kg/s) ve uçuş başına yakıt
  features.py  uçuş bazında girdi değişkenleri
scripts/run_pipeline.py   uçtan uca işlem hattı
app/streamlit_app.py      Streamlit arayüzü (iskelet)
notebooks/                keşifsel analiz ve modelleme defterleri
docs/                     proje notları
```

## Varsayımlar

- TAS ≈ yer hızı (rüzgar verisi eklenene kadar).
- Kütle bilinmiyor: kalkışta MTOW × 0,85, inişte MTOW × 0,70 (`fuel.py` içinde `MASS_FRAC`).
- OpenAP'te bulunmayan tipler en yakın vekile eşlenir (`aircraft.py` içinde `FALLBACK`);
  turboproplar (ATR, Q400) hesap dışı kalır.
