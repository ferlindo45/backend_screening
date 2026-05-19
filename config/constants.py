"""
Constants for Stock Screening System
"""

# ============================================================
# COMPANY NAMES MAPPING
# ============================================================
COMPANY_NAMES = {
    'AADI.JK': 'Adi Sarana Armada', 'ADRO.JK': 'Adaro Energy', 'AKRA.JK': 'AKR Corporindo',
    'AMRT.JK': 'Sumber Alfaria Trijaya', 'ANTM.JK': 'Aneka Tambang', 'ARTO.JK': 'Bank Artos',
    'ASII.JK': 'Astra International', 'BBCA.JK': 'Bank Central Asia', 'BBNI.JK': 'Bank Negara Indonesia',
    'BBRI.JK': 'Bank Rakyat Indonesia', 'BMRI.JK': 'Bank Mandiri', 'CPIN.JK': 'Charoen Pokphand Indonesia',
    'GOTO.JK': 'GoTo Gojek Tokopedia', 'ICBP.JK': 'Indofood CBP', 'INDF.JK': 'Indofood Sukses Makmur',
    'TLKM.JK': 'Telkom Indonesia', 'UNVR.JK': 'Unilever Indonesia', 'UNTR.JK': 'United Tractors',
    'PGAS.JK': 'Perusahaan Gas Negara', 'PTBA.JK': 'Bukit Asam', 'SMGR.JK': 'Semen Indonesia',
    'TOWR.JK': 'Sarana Menara Nusantara', 'EXCL.JK': 'XL Axiata', 'ISAT.JK': 'Indosat Ooredoo',
    'MEDC.JK': 'Medco Energi Internasional', 'JPFA.JK': 'Japfa Comfeed', 'KLBF.JK': 'Kalbe Farma',
    'MAPI.JK': 'Mitra Adiperkasa', 'MDKA.JK': 'Merdeka Copper Gold', 'INCO.JK': 'Vale Indonesia',
    'ITMG.JK': 'Indo Tambangraya Megah', 'ADMR.JK': 'Adaro Minerals', 'AMMN.JK': 'Amman Mineral',
    'BREN.JK': 'Barito Renewables', 'BRPT.JK': 'Barito Pacific', 'BUMI.JK': 'Bumi Resources',
    'CTRA.JK': 'Ciputra Development', 'DSSA.JK': 'Dian Swastatika', 'EMTK.JK': 'Elang Mahkota Teknologi',
    'HEAL.JK': 'Medikaloka Hermina', 'INKP.JK': 'Indah Kiat Pulp & Paper', 'MBMA.JK': 'Merdeka Battery Materials',
    'NCKL.JK': 'Trimegah Bangun Persada', 'PGEO.JK': 'Pertamina Geothermal', 'SCMA.JK': 'Surya Citra Media',
    'TBIG.JK': 'Tower Bersama Infrastructure', 'TINS.JK': 'Timah', 'TKIM.JK': 'Pabrik Kertas Tjiwi Kimia',
    'BYAN.JK': 'Bayan Resources', 'BBTN.JK': 'Bank Tabungan Negara', 'PWON.JK': 'Pakuwon Jati',
    'PTPP.JK': 'PP Properti', 'BRIS.JK': 'Bank Syariah Indonesia', 'BDMN.JK': 'Bank Danamon',
    'BSDE.JK': 'Bumi Serpong Damai', 'BUKA.JK': 'Bukalapak', 'HRUM.JK': 'Harum Energy',
    'MIKA.JK': 'Mitra Keluarga Karyasehat', 'MNCN.JK': 'Media Nusantara Citra', 'SMRA.JK': 'Summarecon Agung',
    'GGRM.JK': 'Gudang Garam', 'ERAA.JK': 'Erajaya Swasembada'
}

# ============================================================
# RULE-BASED SENTIMENT KEYWORDS
# ============================================================
NEGATIVE_KEYWORDS = {
    'anjlok': -0.45, 'ambruk': -0.45, 'tumbang': -0.45, 'runtuh': -0.45,
    'phk': -0.40, 'pemutusan hubungan kerja': -0.40, 'likuidasi': -0.45,
    'bangkrut': -0.50, 'default': -0.45, 'delisting': -0.50, 'suspensi': -0.40,
    'turun': -0.25, 'jatuh': -0.30, 'rugi': -0.30, 'merosot': -0.35,
    'penurunan': -0.25, 'krisis': -0.35, 'buruk': -0.25, 'melemah': -0.25,
    'lesu': -0.25, 'tertekan': -0.25, 'anjlog': -0.35, 'rendah': -0.20,
    'hutang': -0.20, 'net sell': -0.30, 'investor asing cabut': -0.35,
    'tidak bayar': -0.30, 'denda': -0.20, 'sanksi': -0.25, 'koreksi': -0.15,
    'warning': -0.20, 'waswas': -0.20, 'waspada': -0.15, 'bearish': -0.35,
    'tekanan jual': -0.35, 'buang saham': -0.40, 'masif': -0.15, 'longsor': -0.45,
    'pangkas': -0.20, 'negatif': -0.25, 'hancur': -0.45, 'stagnan': -0.05,
    'oversold': 0.10, # Oversold bisa jadi sinyal beli teknikal tapi sentimen buruk
}

POSITIVE_KEYWORDS = {
    'lompat': 0.40, 'melonjak': 0.40, 'terbang': 0.45, 'rekor': 0.40,
    'tertinggi': 0.35, 'dividen': 0.35, 'buyback': 0.40, 'saham naik': 0.35,
    'naik': 0.25, 'gain': 0.25, 'pertumbuhan': 0.30, 'laba': 0.30,
    'meningkat': 0.25, 'ekspansi': 0.30, 'akuisisi': 0.35, 'kerjasama': 0.20,
    'rating upgrade': 0.40, 'rekomendasi beli': 0.40, 'target price naik': 0.35,
    'stabil': 0.15, 'positif': 0.25, 'optimis': 0.25, 'prospek': 0.20,
    'cerah': 0.25, 'net buy': 0.35, 'beli': 0.20, 'bullish': 0.40,
    'akumulasi': 0.30, 'borong': 0.35, 'rebound': 0.30, 'cuan': 0.30,
    'proyeksi': 0.15, 'overweight': 0.30, 'outperform': 0.30,
}
