# 8 – 2. Project Topic (C) + 3.4 ML Methods için devir notu

Bölüm 3.2'den (veri ön işleme) sana geçen bilgiler. Kurulum ve çalıştırma için ana [README](../README.md) dosyasına bak.

## Veri

- **Ana tablo:** `processed/discharge_cycles.csv`. Bir satır bir deşarj döngüsü; 34 batarya, 2,738 döngü.
- **Hedefe aday sütun:** `capacity_ah`. SOH (sağlık durumu) bundan türetilir; nominal kapasite 2 Ah.
- **Döngü düzeyindeki özellikler:** `cycle_number`, `duration_s` (deşarj süresi), `v_min` (en düşük voltaj), `t_max` (en yüksek hücre sıcaklığı), `ambient_temperature`.
- **Daha fazla özellik gerekirse:** `discharge_clean.parquet` ve `charge_clean.parquet` dosyalarında ham zaman serileri var.

## Dikkat

1. **`cycles_left` gerçek RUL değil.** Bu sütun "deney durdurulana kadar kalan döngü" sayısını tutuyor, bataryanın ömrünün bitmesine kalan döngüyü değil.
   - **B0005:** 126. döngüde kapasite 1.4 Ah'in altına düşmüş, yani ömrü bitmiş. Deney ise 169. döngüye kadar sürmüş. Ömrünün bittiği anda `cycles_left` hâlâ 43.
   - **B0025–B0032:** hâlâ sağlamken (1.56–1.77 Ah) durdurulmuş.

   RUL hedefini hangi tanımla kuracağın senin kararın, ama bu farkı 3.4'te yazman gerekiyor. Detaylar tezde 3.2.4'te.
2. **`cycle_number` 0 olan döngü gerçek bir kapasite ölçümü değil.** 23 bataryada ilk deşarj, ilk şarjdan önce yapılmış; bataryanın depodan geldiği halini ölçüyor. 23'ün 19'unda değer bir sonraki döngüden düşük. Eğitimde bu satırları çıkar: `c[c.cycle_number > 0]`.
3. **Ömür sonu eşiği (1.4 Ah) her bataryada anlamlı değil.** 0. döngü hariç tutulduğunda bile şu bataryalar 1.4 Ah'in altında başlıyor: B0033, B0038–B0041, B0045, B0051 ve B0053–B0056. Bu bataryalar ilk döngüden itibaren "ömrü bitmiş" görünür.
4. **B0050'de bir hasar olayı var.** `cycle_id` 10–14 arasında kapasite 0.03 Ah'ten 2.64 Ah'e çıkıyor. Bu döngüler normal yaşlanmayı yansıtmıyor.
5. **Veri sızıntısı riski:** eğitim ve test verisini **bataryaya göre** ayır. Aynı batarya iki tarafta da olursa model komşu döngüleri ezberler ve sonuçlar olduğundan iyi çıkar.
6. **Koşullar farklı:** ortam sıcaklıkları 4, 22, 24, 43 ve 44 °C. Altı batarya (B0038–B0040, B0042–B0044) iki farklı sıcaklıkta test edildi. Modeli tüm bataryalarla mı, yoksa sadece aynı koşuldaki bataryalarla mı eğiteceğini belirt.
7. **Literatürde en çok kullanılan bataryalar B0005, B0006, B0007 ve B0018.** Hepsi 24 °C'de test edilmiş. Başka çalışmalarla karşılaştırma yapacaksan bu dördünü kullan.
