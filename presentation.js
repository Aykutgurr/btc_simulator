const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "BTC Futures Trading Simulator";
pres.author = "BTC Simulator Team";

// ─── PALETTE ───────────────────────────────────────────────────────────────
const C = {
  dark:    "0A1628",   // deep navy (title / dark slides)
  navy:    "112240",   // slightly lighter navy
  card:    "1A2F4A",   // card bg on dark slides
  light:   "F8FAFC",   // content slide bg
  cardL:   "FFFFFF",   // card on light slides
  orange:  "F7931A",   // Bitcoin orange – primary accent
  cyan:    "22D3EE",   // secondary accent
  teal:    "0D9488",   // tertiary accent
  green:   "22C55E",
  red:     "EF4444",
  textD:   "1E293B",   // dark text for light slides
  textL:   "F1F5F9",   // light text for dark slides
  muted:   "94A3B8",   // muted text
  mutedD:  "64748B",
  divider: "E2E8F0",
};

// ─── HELPERS ───────────────────────────────────────────────────────────────
function darkBg(slide) {
  slide.background = { color: C.dark };
}
function lightBg(slide) {
  slide.background = { color: C.light };
}

// Slide section badge (top-left, dark slides)
function badge(slide, label) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.45, y: 0.3, w: 1.9, h: 0.32,
    fill: { color: C.orange }, line: { color: C.orange },
    rectRadius: 0.06,
  });
  slide.addText(label.toUpperCase(), {
    x: 0.45, y: 0.3, w: 1.9, h: 0.32,
    fontSize: 8.5, bold: true, color: "FFFFFF",
    align: "center", valign: "middle", margin: 0,
  });
}

// Section badge for light slides
function badgeL(slide, label) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.45, y: 0.28, w: 2.1, h: 0.32,
    fill: { color: C.orange }, line: { color: C.orange },
    rectRadius: 0.06,
  });
  slide.addText(label.toUpperCase(), {
    x: 0.45, y: 0.28, w: 2.1, h: 0.32,
    fontSize: 8.5, bold: true, color: "FFFFFF",
    align: "center", valign: "middle", margin: 0,
  });
}

// Big heading (dark slides)
function heading(slide, text, y = 0.75) {
  slide.addText(text, {
    x: 0.45, y, w: 9.1, h: 0.65,
    fontSize: 28, bold: true, color: C.textL,
    align: "left", valign: "middle", margin: 0,
  });
}

// Big heading (light slides)
function headingL(slide, text, y = 0.72) {
  slide.addText(text, {
    x: 0.45, y, w: 9.1, h: 0.65,
    fontSize: 26, bold: true, color: C.textD,
    align: "left", valign: "middle", margin: 0,
  });
}

// Orange accent dot
function dot(slide, x, y, color = C.orange) {
  slide.addShape(pres.shapes.OVAL, {
    x, y, w: 0.13, h: 0.13, fill: { color }, line: { color },
  });
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 1 – TITLE
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  darkBg(s);

  // Left accent bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.22, h: 5.625,
    fill: { color: C.orange }, line: { color: C.orange },
  });

  // Big circle decoration (top right)
  s.addShape(pres.shapes.OVAL, {
    x: 7.6, y: -1.0, w: 4.2, h: 4.2,
    fill: { color: "112240" }, line: { color: "1E3D6B", width: 2 },
  });
  s.addShape(pres.shapes.OVAL, {
    x: 8.2, y: -0.4, w: 3.0, h: 3.0,
    fill: { color: C.orange, transparency: 85 }, line: { color: C.orange, transparency: 70 },
  });

  // ₿ symbol
  s.addText("₿", {
    x: 8.5, y: 0.05, w: 2.2, h: 1.6,
    fontSize: 72, bold: true, color: C.orange, align: "center", valign: "middle",
  });

  // Title
  s.addText("BTC Futures", {
    x: 0.55, y: 1.6, w: 7.5, h: 0.85,
    fontSize: 48, bold: true, color: C.textL, align: "left", margin: 0,
  });
  s.addText("Trading Simulator", {
    x: 0.55, y: 2.4, w: 7.5, h: 0.85,
    fontSize: 48, bold: true, color: C.orange, align: "left", margin: 0,
  });

  // Subtitle
  s.addText("Yapay Zeka Destekli Bitcoin Vadeli İşlem Simülasyon Platformu", {
    x: 0.55, y: 3.35, w: 8.5, h: 0.42,
    fontSize: 15, color: C.muted, align: "left", margin: 0, italic: true,
  });

  // Divider
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.55, y: 3.85, w: 4.5, h: 0.04,
    fill: { color: C.orange, transparency: 40 }, line: { color: C.orange, transparency: 40 },
  });

  // Tags
  const tags = ["Gerçek Zamanlı Simülasyon", "AI Bot Üretimi", "Çoklu Strateji"];
  tags.forEach((t, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.55 + i * 3.0, y: 4.15, w: 2.7, h: 0.35,
      fill: { color: C.card }, line: { color: "2A4A6E" }, rectRadius: 0.1,
    });
    s.addText(t, {
      x: 0.55 + i * 3.0, y: 4.15, w: 2.7, h: 0.35,
      fontSize: 10, color: C.cyan, align: "center", valign: "middle", margin: 0,
    });
  });

  s.addNotes(`KONUŞMA METNİ:
Merhaba, ben [İsim]. Bugün sizlere geliştirdiğimiz BTC Futures Trading Simulator'ı tanıtacağım.
Bu platform, Bitcoin vadeli işlem piyasasında strateji geliştirmek isteyen herkesin gerçek para riske atmadan test edebileceği, yapay zeka destekli bir simülasyon ortamıdır.
Sunum yaklaşık 12-15 dakika sürecek. Önce problemi, ardından çözümümüzü ve inovatif yanlarını aktaracağım.`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 2 – PROBLEM: KRİPTO YATIRIMCISININ DÜNYASI
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  darkBg(s);
  badge(s, "Problem Tanımı");
  heading(s, "Kripto Piyasası: Yüksek Fırsat, Yüksek Risk");

  // Stats row
  const stats = [
    { val: "%80", lbl: "Yeni yatırımcı\nilk yılda zarar eder" },
    { val: "100x", lbl: "Kaldıraç riski\nvadeli işlemlerde" },
    { val: "$500M+", lbl: "Yanlış strateji\nnedeniyle kaybedilen sermaye" },
  ];
  stats.forEach((st, i) => {
    const x = 0.45 + i * 3.2;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.55, w: 2.95, h: 1.9,
      fill: { color: C.card }, line: { color: "1E3A5F" },
    });
    // Top orange stripe
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.55, w: 2.95, h: 0.06,
      fill: { color: C.orange }, line: { color: C.orange },
    });
    s.addText(st.val, {
      x, y: 1.75, w: 2.95, h: 0.75,
      fontSize: 36, bold: true, color: C.orange, align: "center", margin: 0,
    });
    s.addText(st.lbl, {
      x, y: 2.52, w: 2.95, h: 0.75,
      fontSize: 12, color: C.muted, align: "center", valign: "top", margin: 0,
    });
  });

  // Pain points
  s.addText("Temel Zorluklar:", {
    x: 0.45, y: 3.6, w: 9.1, h: 0.35,
    fontSize: 13, bold: true, color: C.textL, margin: 0,
  });

  const pains = [
    "Gerçek piyasada strateji testi = gerçek para kaybı",
    "Kaldıraçlı işlemlerde küçük hatalar büyük kayıplara yol açar",
    "Algoritmik strateji geliştirmek programlama bilgisi gerektirir",
    "Geçmiş veriye göre test (backtest) yapmak zaman alır ve uzmanlık ister",
  ];
  s.addText(pains.map((p, i) => ({
    text: p,
    options: { bullet: true, breakLine: i < pains.length - 1, fontSize: 12.5, color: C.textL },
  })), { x: 0.55, y: 4.0, w: 9.0, h: 1.4 });

  s.addNotes(`KONUŞMA METNİ:
Kripto para piyasası büyük fırsatlar sunarken, aynı zamanda son derece riskli bir alan.
Araştırmalar, yeni yatırımcıların büyük çoğunluğunun ilk yılda zarar ettiğini gösteriyor.
Özellikle Bitcoin vadeli işlemleri —yani futures— kaldıraçlı yapısı nedeniyle en riskli araçlardan biri.
Sorun şu: Bir stratejiyi test etmenin tek yolu ya gerçek para yatırmak, ya da karmaşık yazılım araçlarıyla boğuşmak.
Peki bu ikisi arasında başka bir yol yok mu?`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 3 – PROBLEM: MEVCUT ARAÇLARIN EKSİKLİKLERİ
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  lightBg(s);
  badgeL(s, "Problem Tanımı");
  headingL(s, "Mevcut Çözümler Neden Yetersiz?");

  // 2x2 grid
  const items = [
    { icon: "📊", title: "Geleneksel Backtesting Araçları", desc: "Sadece geçmiş verileri gösterir, canlı simülasyon yapmaz. Kullanıcıyı kendi başına bırakır." },
    { icon: "💸", title: "Demo Hesaplar", desc: "Gerçek piyasa koşullarını yansıtmaz. Kaldıraç ve likidisyon mekanizmaları eksik ya da sahte." },
    { icon: "🤖", title: "Algoritmik Trading Platformları", desc: "Yüksek teknik engel: kod yazabilmek zorunlu. Başlangıç seviyesi için erişilemez." },
    { icon: "📱", title: "Borsa Uygulamaları", desc: "Eğitim amaçlı değil. Kullanıcıyı gerçek risk almaya yönlendirir." },
  ];

  items.forEach((item, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.45 + col * 4.85;
    const y = 1.55 + row * 1.85;

    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 4.6, h: 1.65,
      fill: { color: C.cardL },
      line: { color: C.divider },
      shadow: { type: "outer", color: "000000", blur: 8, offset: 2, angle: 135, opacity: 0.08 },
    });
    // Red left stripe = problem indicator
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 0.07, h: 1.65,
      fill: { color: C.red }, line: { color: C.red },
    });
    s.addText(item.icon + "  " + item.title, {
      x: x + 0.18, y: y + 0.12, w: 4.3, h: 0.38,
      fontSize: 12.5, bold: true, color: C.textD, margin: 0,
    });
    s.addText(item.desc, {
      x: x + 0.18, y: y + 0.5, w: 4.3, h: 1.0,
      fontSize: 11, color: C.mutedD, margin: 0,
    });
  });

  // Bottom callout
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.45, y: 5.05, w: 9.1, h: 0.38,
    fill: { color: "FFF7ED" }, line: { color: "FED7AA" },
  });
  s.addText("⚡  Eksik olan şey: Gerçekçi + Erişilebilir + Yapay Zeka Destekli bir platform", {
    x: 0.55, y: 5.05, w: 9.0, h: 0.38,
    fontSize: 12, bold: true, color: "92400E", align: "center", valign: "middle", margin: 0,
  });

  s.addNotes(`KONUŞMA METNİ:
Piyasada birçok araç var, fakat hiçbiri bütünsel bir çözüm sunmuyor.
Geleneksel backtesting araçları statik: geçmişe bakıyorsunuz, ama gerçek zamanlı bir simülasyon yok.
Demo hesaplar borsa tarafından sunuluyor ve çoğu zaman kaldıraç mekanizmaları gerçekçi değil.
Algoritmik platformlar ise çok teknik: strateji geliştirmek için Python veya C++ bilmek gerekiyor.
Biz bu boşluğu doldurmak istedik.`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 4 – ÇÖZÜM: PROJENİN AMACI
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  darkBg(s);
  badge(s, "Çözüm");
  heading(s, "BTC Futures Simulator Nedir?");

  // Center big quote / value prop
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.45, y: 1.55, w: 9.1, h: 1.5,
    fill: { color: C.card }, line: { color: "1E3A5F" },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.45, y: 1.55, w: 0.08, h: 1.5,
    fill: { color: C.orange }, line: { color: C.orange },
  });
  s.addText('"Gercek parayi riske atmadan, Bitcoin vadeli islem stratejilerini canli piyasa kosullarinda test edip gelistirebileceginiz, yapay zeka destekli bir simulasyon platformu."', {
    x: 0.65, y: 1.6, w: 8.7, h: 1.4,
    fontSize: 16, color: C.textL, italic: true, align: "left", valign: "middle", margin: 0,
  });

  // 3 pillars
  const pillars = [
    { icon: "🎯", title: "Güvenli Test Ortamı", desc: "Gerçek piyasa dinamikleriyle aynı şartlarda, sıfır finansal risk ile strateji deneyin" },
    { icon: "🤖", title: "AI Bot Üretici", desc: "Stratejinizi Türkçe/İngilizce yazın, yapay zeka sizin için hazır bir trading botu oluşturur" },
    { icon: "📈", title: "Detaylı Analiz", desc: "Kazanma oranı, Sharpe ratio, maksimum düşüş ve daha fazlası ile stratejinizi ölçün" },
  ];

  pillars.forEach((p, i) => {
    const x = 0.45 + i * 3.22;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 3.3, w: 3.0, h: 2.1,
      fill: { color: C.card }, line: { color: "1E3A5F" },
    });
    s.addShape(pres.shapes.OVAL, {
      x: x + 1.1, y: 3.2, w: 0.8, h: 0.8,
      fill: { color: C.orange }, line: { color: C.orange },
    });
    s.addText(p.icon, {
      x: x + 1.1, y: 3.2, w: 0.8, h: 0.8,
      fontSize: 20, align: "center", valign: "middle", margin: 0,
    });
    s.addText(p.title, {
      x, y: 4.1, w: 3.0, h: 0.45,
      fontSize: 12.5, bold: true, color: C.textL, align: "center", margin: 0,
    });
    s.addText(p.desc, {
      x: x + 0.1, y: 4.55, w: 2.8, h: 0.8,
      fontSize: 10.5, color: C.muted, align: "center", valign: "top", margin: 0,
    });
  });

  s.addNotes(`KONUŞMA METNİ:
İşte biz bunu inşa ettik: BTC Futures Trading Simulator.
Özünde üç şey yapıyor:
Birincisi, gerçek piyasa koşullarını simüle ediyor — kaldıraç, likidisyon, komisyon, gerçek Bitcoin fiyat verileri... hepsi var.
İkincisi, yapay zeka destekli bot üretici sayesinde programlama bilgisi olmayan biri bile kendi strateji botunu oluşturabiliyor.
Üçüncüsü, her stratejiyi bilimsel metriklerle ölçüp karşılaştırabiliyorsunuz.`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 5 – NASIL ÇALIŞIR (GENEL BAKIŞ)
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  lightBg(s);
  badgeL(s, "Nasıl Çalışır?");
  headingL(s, "Platform İş Akışı");

  // Flow: 4 steps
  const steps = [
    { n: "1", title: "Veri Yükle", desc: "Bitcoin geçmiş fiyat verisi (CSV) veya canlı veri ile simülasyonu başlatın" },
    { n: "2", title: "Strateji Seç", desc: "Hazır botlardan birini seçin ya da AI ile kendinize özel bir bot oluşturun" },
    { n: "3", title: "Simüle Et", desc: "Gerçekçi piyasa koşullarında pozisyon açın, botları çalıştırın" },
    { n: "4", title: "Analiz Et", desc: "Sonuçları inceleyin, stratejiyi iyileştirin ve tekrar test edin" },
  ];

  steps.forEach((step, i) => {
    const x = 0.45 + i * 2.35;
    // Box
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.55, w: 2.15, h: 2.8,
      fill: { color: C.cardL }, line: { color: C.divider },
      shadow: { type: "outer", color: "000000", blur: 8, offset: 2, angle: 135, opacity: 0.08 },
    });
    // Number circle
    s.addShape(pres.shapes.OVAL, {
      x: x + 0.62, y: 1.68, w: 0.9, h: 0.9,
      fill: { color: C.orange }, line: { color: C.orange },
    });
    s.addText(step.n, {
      x: x + 0.62, y: 1.68, w: 0.9, h: 0.9,
      fontSize: 24, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0,
    });
    s.addText(step.title, {
      x, y: 2.7, w: 2.15, h: 0.45,
      fontSize: 13, bold: true, color: C.textD, align: "center", margin: 0,
    });
    s.addText(step.desc, {
      x: x + 0.1, y: 3.2, w: 1.95, h: 1.1,
      fontSize: 11, color: C.mutedD, align: "center", valign: "top", margin: 0,
    });
    // Arrow between steps
    if (i < 3) {
      s.addShape(pres.shapes.RECTANGLE, {
        x: x + 2.15, y: 1.96, w: 0.2, h: 0.04,
        fill: { color: C.orange }, line: { color: C.orange },
      });
      s.addText("→", {
        x: x + 2.12, y: 1.85, w: 0.23, h: 0.26,
        fontSize: 16, color: C.orange, align: "center", valign: "middle", margin: 0,
      });
    }
  });

  // Bottom note
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.45, y: 4.65, w: 9.1, h: 0.7,
    fill: { color: "EFF6FF" }, line: { color: "BFDBFE" },
  });
  s.addText("💡  Bu döngü sürekli tekrarlanabilir — her iterasyonda strateji daha da gelişir. Gerçek paranız güvende.", {
    x: 0.6, y: 4.65, w: 8.9, h: 0.7,
    fontSize: 12.5, color: "1E40AF", align: "left", valign: "middle", margin: 0,
  });

  s.addNotes(`KONUŞMA METNİ:
Platform dört basit adımda çalışıyor.
Önce veri yüklüyorsunuz — gerçek Bitcoin geçmiş verileri veya yfinance üzerinden anlık veri.
Sonra strateji seçiyorsunuz — sistemde hazır botlar var ya da siz kendinizinki oluşturabiliyorsunuz.
Simülasyonu başlatıyorsunuz: platform sanki gerçek bir borsa gibi davranıyor.
Son olarak sonuçları analiz ediyorsunuz.
Ve bu döngüyü istediğiniz kadar tekrarlayabilirsiniz.`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 6 – ÖZELLİK: GERÇEKÇİ SİMÜLASYON
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  darkBg(s);
  badge(s, "Temel Özellik");
  heading(s, "Gerçekçi Piyasa Simülasyonu");

  const features = [
    { icon: "⚡", title: "Kaldıraç (1x – 20x)", desc: "Gerçek borsa koşullarını yansıtan kaldıraçlı pozisyonlar" },
    { icon: "💥", title: "Likidisyon Motoru", desc: "Marjin yetersiz kalırsa pozisyon otomatik kapatılır — tıpkı gerçek borsada" },
    { icon: "🛑", title: "Stop-Loss / Take-Profit", desc: "Risk yönetimi emirleri otomatik çalışır, strateji belirlediğiniz limitlere uyar" },
    { icon: "📉", title: "Çoklu Zaman Dilimi", desc: "1 dakika, 5 dk, 15 dk, 1 saat ve 4 saatlik grafik verileri eş zamanlı" },
    { icon: "📊", title: "Komisyon Takibi", desc: "Gerçek borsa komisyon oranları ile net karlılık hesabı" },
    { icon: "⏩", title: "Hız Kontrolü", desc: "Normal, 10x, 100x ve maksimum hız ile simülasyonu hızlandırın" },
  ];

  features.forEach((f, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.45 + col * 3.22;
    const y = 1.55 + row * 1.85;

    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 3.0, h: 1.65,
      fill: { color: C.card }, line: { color: "1E3A5F" },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 3.0, h: 0.06,
      fill: { color: C.cyan }, line: { color: C.cyan },
    });
    s.addText(f.icon + "  " + f.title, {
      x: x + 0.12, y: y + 0.12, w: 2.76, h: 0.42,
      fontSize: 12, bold: true, color: C.textL, margin: 0,
    });
    s.addText(f.desc, {
      x: x + 0.12, y: y + 0.54, w: 2.76, h: 0.9,
      fontSize: 10.5, color: C.muted, margin: 0,
    });
  });

  s.addNotes(`KONUŞMA METNİ:
Sistemin en kritik özelliği gerçekçiliği.
Gerçek borsada ne varsa burada da var: kaldıraç, likidisyon, stop-loss, take-profit.
Örneğin 10x kaldıraçla Bitcoin alırsanız ve fiyat %10 düşerse — gerçek borsada olduğu gibi — pozisyonunuz likide edilir.
Bu deneyimi yaşamak, yatırımcıya çok değerli bir öğretim sağlıyor; üstelik gerçek para kaybetmeden.
Ayrıca simülasyonu 100 kat hızlandırarak aylarca olan geçmişi dakikalar içinde test edebiliyorsunuz.`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 7 – ÖZELLİK: BOT EKOSİSTEMİ
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  lightBg(s);
  badgeL(s, "Temel Özellik");
  headingL(s, "Çoklu Bot Ekosistemi");

  // Left: description
  s.addText("Platform, farklı strateji yaklaşımlarına sahip hazır botlarla birlikte gelir. Botlar birbirinden bağımsız çalışır, aynı anda aktif edilebilir ve gerçek zamanlı karşılaştırılabilir.", {
    x: 0.45, y: 1.5, w: 4.5, h: 1.2,
    fontSize: 13, color: C.textD, margin: 0,
  });

  // Bot type list
  const botTypes = [
    { color: C.orange, label: "Teknik Analiz Botları", desc: "RSI, MACD, EMA gibi indikatörlere dayalı klasik stratejiler" },
    { color: C.cyan, label: "Makine Öğrenmesi Botları", desc: "XGBoost ve derin öğrenme modelleri ile piyasa tahmini" },
    { color: C.teal, label: "ICT Strateji Botları", desc: "Kurumsal işlem teorisi temelli, profesyonel trader yaklaşımı" },
    { color: C.green, label: "Mean Reversion Botları", desc: "Fiyat ortalamaya dönme prensibini kullanan stratejiler" },
  ];

  botTypes.forEach((bt, i) => {
    const y = 1.5 + i * 0.92;
    s.addShape(pres.shapes.OVAL, {
      x: 5.1, y: y + 0.22, w: 0.2, h: 0.2,
      fill: { color: bt.color }, line: { color: bt.color },
    });
    s.addText(bt.label, {
      x: 5.4, y, w: 4.2, h: 0.32,
      fontSize: 12.5, bold: true, color: C.textD, margin: 0,
    });
    s.addText(bt.desc, {
      x: 5.4, y: y + 0.32, w: 4.2, h: 0.45,
      fontSize: 11, color: C.mutedD, margin: 0,
    });
  });

  // Divider
  s.addShape(pres.shapes.RECTANGLE, {
    x: 5.0, y: 1.5, w: 0.04, h: 3.68,
    fill: { color: C.divider }, line: { color: C.divider },
  });

  // Stats at bottom
  const stats = [
    { val: "6+", lbl: "Hazır Bot" },
    { val: "5", lbl: "Zaman Dilimi" },
    { val: "∞", lbl: "AI Bot Üretimi" },
  ];
  stats.forEach((st, i) => {
    const x = 0.45 + i * 1.55;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 5.0, w: 1.4, h: 0.45,
      fill: { color: "FFF7ED" }, line: { color: "FED7AA" },
    });
    s.addText(st.val, {
      x, y: 5.0, w: 1.4, h: 0.24,
      fontSize: 18, bold: true, color: C.orange, align: "center", margin: 0,
    });
    s.addText(st.lbl, {
      x, y: 5.24, w: 1.4, h: 0.21,
      fontSize: 9.5, color: C.mutedD, align: "center", margin: 0,
    });
  });

  s.addNotes(`KONUŞMA METNİ:
Sistemde altıdan fazla hazır trading botu var.
Her biri farklı bir strateji yaklaşımı kullanıyor: klasik teknik analiz, makine öğrenmesi, kurumsal işlem teorisi ve ortalama dönüş stratejisi.
Bunları tek tek veya aynı anda çalıştırıp karşılaştırabiliyorsunuz.
Ama asıl inovatif kısım şurası: sadece hazır botlarla sınırlı değilsiniz.`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 8 – İNOVATİF YÖN: AI BOT ÜRETİCİ
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  darkBg(s);
  badge(s, "İnovatif Yön");
  heading(s, "Yapay Zeka ile Kendi Botunu Yarat");

  // Left column: steps
  const steps = [
    { n: "1", text: "Strateji fikrinizi doğal dilde yazın\n(Türkçe veya İngilizce)" },
    { n: "2", text: "Yapay zeka (yerel LLM) Python kodu\notomatik olarak üretir" },
    { n: "3", text: "Kod güvenlik kontrolünden ve\nsentaks doğrulamasından geçer" },
    { n: "4", text: "Sandbox ortamında test edilir,\nsonuçlar anlık raporlanır" },
    { n: "5", text: "Onayladığınızda bot sisteme\neklenir ve simülasyonda çalışır" },
  ];

  steps.forEach((step, i) => {
    const y = 1.5 + i * 0.78;
    s.addShape(pres.shapes.OVAL, {
      x: 0.45, y: y + 0.05, w: 0.48, h: 0.48,
      fill: { color: C.orange }, line: { color: C.orange },
    });
    s.addText(step.n, {
      x: 0.45, y: y + 0.05, w: 0.48, h: 0.48,
      fontSize: 14, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0,
    });
    if (i < steps.length - 1) {
      s.addShape(pres.shapes.RECTANGLE, {
        x: 0.68, y: y + 0.53, w: 0.04, h: 0.28,
        fill: { color: "2A4A6E" }, line: { color: "2A4A6E" },
      });
    }
    s.addText(step.text, {
      x: 1.1, y, w: 4.1, h: 0.62,
      fontSize: 12, color: C.textL, valign: "middle", margin: 0,
    });
  });

  // Right: example prompt box
  s.addShape(pres.shapes.RECTANGLE, {
    x: 5.5, y: 1.45, w: 4.1, h: 3.9,
    fill: { color: "0D1B2A" }, line: { color: "1E3A5F" },
  });
  // Header bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 5.5, y: 1.45, w: 4.1, h: 0.42,
    fill: { color: C.card }, line: { color: "1E3A5F" },
  });
  s.addText("⚙  AI Bot Üretici", {
    x: 5.6, y: 1.45, w: 3.9, h: 0.42,
    fontSize: 11, bold: true, color: C.cyan, valign: "middle", margin: 0,
  });

  s.addText("Bot Adı:", {
    x: 5.65, y: 1.97, w: 1.2, h: 0.28,
    fontSize: 10, color: C.muted, margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.8, y: 1.97, w: 2.65, h: 0.28,
    fill: { color: C.card }, line: { color: "2A4A6E" },
  });
  s.addText("Momentum_Bot_v1", {
    x: 6.85, y: 1.97, w: 2.55, h: 0.28,
    fontSize: 10, color: C.cyan, valign: "middle", margin: 0,
  });

  s.addText("Strateji Açıklaması:", {
    x: 5.65, y: 2.35, w: 3.8, h: 0.25,
    fontSize: 10, color: C.muted, margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 5.65, y: 2.62, w: 3.8, h: 1.45,
    fill: { color: C.card }, line: { color: "2A4A6E" },
  });
  s.addText('"RSI 14 periyot kullan. RSI 30\'un altına düştüğünde long gir, 70\'in üzerine çıktığında short aç. Stop-loss %2, take-profit %4 olsun."', {
    x: 5.72, y: 2.68, w: 3.65, h: 1.33,
    fontSize: 10.5, color: C.textL, italic: true, margin: 0,
  });

  s.addShape(pres.shapes.RECTANGLE, {
    x: 5.65, y: 4.15, w: 3.8, h: 0.38,
    fill: { color: C.orange }, line: { color: C.orange },
  });
  s.addText("🤖  Bot Üret", {
    x: 5.65, y: 4.15, w: 3.8, h: 0.38,
    fontSize: 12, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0,
  });

  s.addText("✦  Programlama bilgisi gerekmez", {
    x: 5.5, y: 4.68, w: 4.1, h: 0.32,
    fontSize: 10.5, color: C.green, align: "center", valign: "middle", margin: 0,
  });

  s.addNotes(`KONUŞMA METNİ:
İşte platformun en inovatif özelliği: Yapay Zeka ile Bot Üretici.
Düşünün: strateji fikrinizi normal bir cümleyle yazıyorsunuz — "RSI 30'un altına düşünce al, 70'in üstüne çıkınca sat" gibi.
Yapay zeka bu açıklamayı alıp otomatik olarak çalışan bir Python botu üretiyor.
Üretilen kod güvenlik kontrolünden geçiyor, test ediliyor, sonra sisteme ekleniyor.
Sıfır programlama bilgisi. Tamamen doğal dil ile bot oluşturabiliyorsunuz.
Bu, kripto dünyasında daha önce böylesine erişilebilir hale getirilmemiş bir şey.`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 9 – ARAYÜZ: GRAFİK & TİCARET (EKRAN GÖRÜNTÜSÜ)
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  darkBg(s);
  badge(s, "Uygulama Demosu");
  heading(s, "Grafik & İşlem Paneli");

  // Screenshot placeholder
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.45, y: 1.5, w: 7.2, h: 3.9,
    fill: { color: C.card }, line: { color: "2A4A6E", width: 2 },
  });
  s.addText("[EKRAN GÖRÜNTÜSܠ]\n\nUygulamayı başlatın → ilk sekme (Grafik & İşlem)\nTarayıcıda: http://localhost:5173\nF12 ekran görüntüsü alın veya CMD+SHIFT+4 (Mac)", {
    x: 0.65, y: 2.2, w: 6.8, h: 2.5,
    fontSize: 13, color: C.muted, align: "center", valign: "middle", italic: true, margin: 0,
  });

  // Right: highlights
  const items = [
    { t: "📈 Mum Grafik", d: "Gerçek zamanlı Bitcoin candlestick grafiği" },
    { t: "📊 Teknik İndikatörler", d: "RSI, MACD, EMA20, EMA50, Hacim" },
    { t: "💼 İşlem Paneli", d: "Long/Short emirleri, kaldıraç ayarı, marjin girişi" },
    { t: "📋 İşlem Geçmişi", d: "Açık/kapalı pozisyonlar, karlılık bilgisi" },
  ];

  items.forEach((item, i) => {
    const y = 1.55 + i * 0.9;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 7.8, y, w: 1.95, h: 0.78,
      fill: { color: C.card }, line: { color: "1E3A5F" },
    });
    s.addText(item.t, {
      x: 7.88, y: y + 0.05, w: 1.79, h: 0.3,
      fontSize: 10, bold: true, color: C.cyan, margin: 0,
    });
    s.addText(item.d, {
      x: 7.88, y: y + 0.35, w: 1.79, h: 0.38,
      fontSize: 9, color: C.muted, margin: 0,
    });
  });

  s.addNotes(`KONUŞMA METNİ:
Şimdi arayüzü görelim.
[EKRAN GÖRÜNTÜSÜNܠ BURAYA EKLEYIN: Uygulamayı çalıştırın, tarayıcıda localhost:5173'ü açın, birinci sekme olan "Grafik & İşlem" sayfasının ekran görüntüsünü alın]
İlk sekmede tam bir borsa arayüzü görüyorsunuz.
Sol üstte gerçek zamanlı mum grafik. Teknik indikatörler — RSI, MACD, hareketli ortalamalar — grafiğin üzerinde.
Sağda ise işlem paneli: buradan long veya short pozisyon açabilir, kaldıraç oranınızı belirleyebilir, stop-loss koyabilirsiniz.
Alt tarafta ise açık ve kapanmış işlemlerinizin listesi.`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 10 – ARAYÜZ: BOT YÖNETİMİ (EKRAN GÖRÜNTÜSÜ)
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  darkBg(s);
  badge(s, "Uygulama Demosu");
  heading(s, "Bot Yönetimi & İstatistikler");

  // Screenshot placeholder
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.45, y: 1.5, w: 7.2, h: 3.9,
    fill: { color: C.card }, line: { color: "2A4A6E", width: 2 },
  });
  s.addText("[EKRAN GÖRÜNTÜSܠ]\n\nİkinci sekme: \"Botlar & İstatistikler\"\nBot listesi görünür haldeyken ekran görüntüsü alın\n\"Yeni Bot Üret\" modalını açık gösterin (opsiyonel)", {
    x: 0.65, y: 2.2, w: 6.8, h: 2.5,
    fontSize: 13, color: C.muted, align: "center", valign: "middle", italic: true, margin: 0,
  });

  // Right panel
  const items = [
    { t: "🤖 Bot Listesi", d: "Aktif/pasif botlar, tek tıkla açma/kapama" },
    { t: "✨ AI Bot Üret", d: "Doğal dil ile yeni strateji botu oluşturma" },
    { t: "📊 Performans", d: "Kazanma oranı, Sharpe, maks. düşüş metrikleri" },
    { t: "📋 Bot Test Raporu", d: "AI bot'un simülasyon test sonuçları" },
  ];
  items.forEach((item, i) => {
    const y = 1.55 + i * 0.9;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 7.8, y, w: 1.95, h: 0.78,
      fill: { color: C.card }, line: { color: "1E3A5F" },
    });
    s.addText(item.t, {
      x: 7.88, y: y + 0.05, w: 1.79, h: 0.3,
      fontSize: 10, bold: true, color: C.orange, margin: 0,
    });
    s.addText(item.d, {
      x: 7.88, y: y + 0.35, w: 1.79, h: 0.38,
      fontSize: 9, color: C.muted, margin: 0,
    });
  });

  s.addNotes(`KONUŞMA METNİ:
İkinci sekmede bot yönetimi var.
[EKRAN GÖRÜNTÜSÜNܠ BURAYA EKLEYIN: "Botlar & İstatistikler" sekmesinin ekran görüntüsünü alın. Mümkünse "Yeni Bot Üret" formunu açık gösterin]
Soldaki listede tüm botlar görünüyor. Her biri için açma/kapama toggle var.
Sağ tarafta strateji performans metrikleri: kazanma oranı yüzde kaç, toplam kar/zarar ne, maksimum düşüş ne olmuş.
"Yeni Bot Üret" butonuna basınca AI bot üretici açılıyor — bunu az önce anlattım.`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 11 – HEDEF KİTLE & KULLANIM SENARYOLARI
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  lightBg(s);
  badgeL(s, "Kime Hitap Ediyor?");
  headingL(s, "Hedef Kitle ve Kullanım Senaryoları");

  const audiences = [
    {
      icon: "🎓",
      title: "Yeni Yatırımcılar",
      color: C.orange,
      items: [
        "Gerçek para riske atmadan öğrenmek",
        "Kaldıraç ve futures kavramlarını anlamak",
        "Strateji geliştirme pratiği yapmak",
      ],
    },
    {
      icon: "📊",
      title: "Deneyimli Traderlar",
      color: C.teal,
      items: [
        "Yeni stratejileri geçmiş veriye karşı test etmek",
        "Birden fazla botu eş zamanlı karşılaştırmak",
        "Performans metriklerini optimize etmek",
      ],
    },
    {
      icon: "🔬",
      title: "Araştırmacılar & Akademisyenler",
      color: C.cyan,
      items: [
        "Algoritmik trading stratejileri üzerine çalışma",
        "ML modellerini piyasa verisinde test etme",
        "Finansal simülasyon verileri üretmek",
      ],
    },
  ];

  audiences.forEach((a, i) => {
    const x = 0.45 + i * 3.22;
    // Card
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.55, w: 3.0, h: 3.7,
      fill: { color: C.cardL }, line: { color: C.divider },
      shadow: { type: "outer", color: "000000", blur: 10, offset: 3, angle: 135, opacity: 0.1 },
    });
    // Top color band
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.55, w: 3.0, h: 0.7,
      fill: { color: a.color }, line: { color: a.color },
    });
    s.addText(a.icon, {
      x, y: 1.55, w: 3.0, h: 0.7,
      fontSize: 24, align: "center", valign: "middle", margin: 0,
    });
    s.addText(a.title, {
      x: x + 0.1, y: 2.35, w: 2.8, h: 0.45,
      fontSize: 13, bold: true, color: C.textD, align: "center", margin: 0,
    });
    a.items.forEach((item, j) => {
      s.addText([{ text: item, options: { bullet: true, fontSize: 11, color: C.textD } }], {
        x: x + 0.15, y: 2.88 + j * 0.68, w: 2.7, h: 0.6,
      });
    });
  });

  s.addNotes(`KONUŞMA METNİ:
Bu platform üç farklı kitleye hitap ediyor.
Birincisi yeni yatırımcılar: bu kitle için en büyük değer, gerçek para kaybetmeden öğrenme fırsatı.
İkincisi deneyimli traderlar: onlar için önemli olan strateji optimizasyonu ve karşılaştırma.
Üçüncüsü araştırmacılar: algoritmik trading ve finans üzerine çalışan akademisyenler için güçlü bir test ortamı.`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 12 – İNOVATİF YÖNLER ÖZET
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  darkBg(s);
  badge(s, "İnovasyon");
  heading(s, "Projeyi Farklı Kılan 4 Özellik");

  const innovations = [
    {
      num: "01",
      title: "Yerel AI Entegrasyonu",
      desc: "Bulut tabanlı API'a bağlı değil. Ollama ile tümüyle yerel LLM (qwen2.5, llama3) kullanılıyor. Veri gizliliği tam olarak korunuyor.",
    },
    {
      num: "02",
      title: "Doğal Dil → Çalışan Kod",
      desc: "Kullanıcının yazdığı strateji açıklaması otomatik olarak test edilmiş, güvenli ve çalışır Python koduna dönüştürülüyor.",
    },
    {
      num: "03",
      title: "Hibrit Bot Mimarisi",
      desc: "Kural tabanlı, makine öğrenmesi ve AI tarafından üretilen botlar aynı motor üzerinde eş zamanlı çalışıyor ve karşılaştırılıyor.",
    },
    {
      num: "04",
      title: "Sandbox Güvenlik Katmanı",
      desc: "AI'nın ürettiği her kod, sisteme eklenmeden önce izole bir ortamda güvenlik ve sözdizimi kontrolünden geçiyor.",
    },
  ];

  innovations.forEach((inn, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.45 + col * 4.85;
    const y = 1.55 + row * 1.95;

    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 4.6, h: 1.75,
      fill: { color: C.card }, line: { color: "1E3A5F" },
    });
    s.addText(inn.num, {
      x: x + 0.18, y: y + 0.18, w: 0.7, h: 0.55,
      fontSize: 22, bold: true, color: C.orange, margin: 0,
    });
    s.addText(inn.title, {
      x: x + 0.9, y: y + 0.18, w: 3.52, h: 0.42,
      fontSize: 13, bold: true, color: C.textL, valign: "middle", margin: 0,
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: x + 0.18, y: y + 0.75, w: 4.24, h: 0.03,
      fill: { color: "1E3A5F" }, line: { color: "1E3A5F" },
    });
    s.addText(inn.desc, {
      x: x + 0.18, y: y + 0.85, w: 4.24, h: 0.82,
      fontSize: 11, color: C.muted, margin: 0,
    });
  });

  s.addNotes(`KONUŞMA METNİ:
Projeyi diğer araçlardan ayıran dört temel inovatif yön var.
Birincisi, yapay zekayı buluta bağlı olmadan yerel olarak çalıştırıyoruz. Bu hem gizliliği koruyor hem de internet bağlantısı gerektirmiyor.
İkincisi, doğal dilden çalışan koda geçiş — bu gerçek anlamda programlama bariyerini ortadan kaldırıyor.
Üçüncüsü, üç farklı bot türünün —kural tabanlı, ML ve AI üretimi— aynı ortamda birlikte çalışması.
Dördüncüsü, güvenlik. AI'nın ürettiği kodun güvenlik kontrolünden geçmeden sisteme eklenmemesi kritik bir özellik.`);
}

// ───────────────────────────────────────────────────────────────────────────
// SLIDE 13 – SONUÇ & GELECEK
// ───────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  darkBg(s);

  // Large orange accent
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.08,
    fill: { color: C.orange }, line: { color: C.orange },
  });

  s.addText("Sonuç", {
    x: 0.5, y: 0.4, w: 9, h: 0.5,
    fontSize: 13, bold: true, color: C.orange, charSpacing: 4, margin: 0,
  });
  s.addText("Bitcoin Futures Trading Simulator\nbir simülasyon değil, bir öğrenme ve geliştirme platformudur.", {
    x: 0.5, y: 0.95, w: 8.5, h: 1.1,
    fontSize: 22, bold: true, color: C.textL, margin: 0,
  });

  // Summary bullets
  const bullets = [
    "✓  Gerçek para riske atmadan piyasa deneyimi",
    "✓  Programlama bilgisi gerektirmeyen AI bot üretimi",
    "✓  Farklı stratejilerin bilimsel metriklerle karşılaştırılması",
    "✓  Tamamen yerel çalışma — veri gizliliği garanti",
  ];
  bullets.forEach((b, i) => {
    s.addText(b, {
      x: 0.5, y: 2.15 + i * 0.5, w: 5.5, h: 0.42,
      fontSize: 13, color: i === 0 ? C.textL : C.muted, margin: 0,
    });
  });

  // Roadmap
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.0, y: 1.45, w: 3.6, h: 3.7,
    fill: { color: C.card }, line: { color: "1E3A5F" },
  });
  s.addText("Gelecek Planları", {
    x: 6.1, y: 1.55, w: 3.4, h: 0.38,
    fontSize: 12, bold: true, color: C.cyan, margin: 0,
  });
  const roadmap = [
    "🌐  Çoklu kripto para desteği",
    "☁️  Bulut tabanlı bot paylaşım platformu",
    "📱  Mobil uygulama",
    "🏆  Bot turnuva modu",
    "📡  Gerçek zamanlı borsa bağlantısı",
  ];
  roadmap.forEach((r, i) => {
    s.addText(r, {
      x: 6.1, y: 2.05 + i * 0.58, w: 3.4, h: 0.5,
      fontSize: 11.5, color: C.muted, margin: 0,
    });
  });

  // Bottom CTA
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.22, w: 10, h: 0.405,
    fill: { color: C.orange }, line: { color: C.orange },
  });
  s.addText("Sorularınız için teşekkür ederim. 🎤", {
    x: 0, y: 5.22, w: 10, h: 0.405,
    fontSize: 14, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0,
  });

  s.addNotes(`KONUŞMA METNİ:
Özetlemek gerekirse: Bu platform üç temel sorunu çözüyor.
Birincisi, yatırımcıları gerçek para kaybetmekten koruyor.
İkincisi, programlama bilgisi olmayan kişilere algoritmik trading kapısını açıyor.
Üçüncüsü, farklı stratejileri bilimsel olarak ölçmenizi sağlıyor.

Gelecekte çoklu kripto para desteği, bulut tabanlı bot paylaşımı ve gerçek borsa entegrasyonu gibi özellikler planlanıyor.

Dinlediğiniz için teşekkür ederim. Sorularınızı alabilirim.`);
}

// ─── WRITE ──────────────────────────────────────────────────────────────────
pres.writeFile({ fileName: "BTC_Simulator_Sunum.pptx" })
  .then(() => console.log("✅ BTC_Simulator_Sunum.pptx oluşturuldu."))
  .catch(e => console.error("❌ Hata:", e));
