# 502531001 Batuhan KOL
# 502531012 Damla SOYDAN

import asyncio  # Asenkron (eşzamanlı olmayan) görevler ve event loop yönetimi için asyncio modülüdür.
import logging  # Debug/log çıktıları üretmek için logging modülü
import sys  # Komut satırı argümanları (sys.argv) ve sistemle ilgili fonksiyonlar için
import time
from urllib.parse import (
    urlparse,
)  # URL'yi parçalarına ayırmak (scheme, host, port, path vs.) için

# aioquic kütüphanesinden QUIC bağlantısı ve protokol sınıfları içe aktarılıyor
from aioquic.asyncio import connect, QuicConnectionProtocol

# HTTP/3 (H3) bağlantısını ve ALPN (Application-Layer Protocol Negotiation) sabitini içe aktarıyoruz
from aioquic.h3.connection import H3Connection, H3_ALPN

# HTTP/3 tarafında oluşabilecek event tipleri: HeadersReceived (başlıklar geldi), DataReceived (veri geldi)
from aioquic.h3.events import HeadersReceived, DataReceived

# QUIC yapılandırma ayarlarını yapabilmek için QuicConfiguration
from aioquic.quic.configuration import QuicConfiguration


# logging sistemini DEBUG seviyesinde başlatıyoruz.
# Bu sayede aioquic içinden gelen debug loglarını da konsolda görebiliriz.
logging.basicConfig(level=logging.DEBUG)


class Http3Client(QuicConnectionProtocol):
    """
    HTTP/3 istemcisi için özel bir protokol sınıfı.
    QuicConnectionProtocol'dan türetiliyor; böylece QUIC event'lerini yakalayıp
    HTTP/3 seviyesinde işleyebiliyoruz.
    """

    def __init__(self, *args, **kwargs):
        self._done = asyncio.Event()
        self.start_time = None
        self.end_time = None
        # Üst (parent) sınıfın kurucusunu çağırıyoruz. QUIC tarafının temel kurulumu burada yapılıyor.
        super().__init__(*args, **kwargs)
        # QUIC bağlantısı (_quic) üzerinde HTTP/3 protokol nesnesi oluşturuyoruz.
        # H3Connection, HTTP/3 çerçevesinde HEADERS/DATA event'lerini yönetiyor.
        self._http = H3Connection(self._quic)
        # Asenkron fonksiyonlarda "iş bitti" sinyali için bir asyncio.Event oluşturuyoruz.
        # BODY tamamen geldiğinde bu event set edilecek.
        self._done = asyncio.Event()
        # Sunucudan gelen HTTP gövdesini (body) toplamak için bir buffer (bytes)
        self._body = b""

    def quic_event_received(self, event):
        """
        QUIC katmanında bir event oluştuğunda aioquic bu fonksiyonu çağırır.
        Buradaki 'event', HTTP/3'e ham QUIC event'i olarak geçilir,
        H3Connection ise bunu HTTP/3 event'lerine dönüştürür.
        """
        # QUIC event'ini HTTP/3 event'lerine çevirip dönen her bir HTTP event'ini işliyoruz.
        for h3_event in self._http.handle_event(event):
            # Eğer gelen event, HTTP/3 HEADERS frame ise (örn: yanıt başlıkları)
            if isinstance(h3_event, HeadersReceived):
                print("\n--- HEADERS ---")
                # h3_event.headers: (key, value) ikililerinden oluşan bir liste (bytes olarak)
                for k, v in h3_event.headers:
                    # bytes -> str çevrilip ekrana yazdırılıyor
                    print(k.decode(), ":", v.decode())
            # Eğer gelen event, HTTP/3 DATA frame ise
            elif isinstance(h3_event, DataReceived):
                # Bu event'teki veri parçasını body buffer'ına ekliyoruz
                self._body += h3_event.data
                # stream_ended: Bu stream için veri akışının tamamen bittiğini söyleyen bayrak
                if h3_event.stream_ended:
                    self.end_time = time.monotonic()
                    # Bütün body geldiği için ekrana yazdırıyoruz
                    print("\n--- BODY ---")
                    # decode(errors="ignore") => UTF-8 hatalarında çökmemek için hatalı karakterleri yok say
                    print(self._body.decode(errors="ignore"))
                    # Artık isteğin işlenmesi bitti, bekleyen coroutine'lere haber veriyoruz
                    self._done.set()

    async def get(self, url):
        self.start_time = time.monotonic()
        """
        Verilen URL'ye HTTP/3 GET isteği atar.
        """
        # URL'yi parçalarına ayır (scheme, netloc, path vb.)
        parsed = urlparse(url)
        # Eğer path boş ise (örn: https://127.0.0.1:4433), varsayılan olarak "/" kullan
        path = parsed.path or "/"
        # QUIC üzerinde yeni bir akış (stream) ID'si alıyoruz.
        # is_unidirectional=False: Bu stream çift yönlü (request/response) kullanılacak demek.
        stream_id = self._quic.get_next_available_stream_id(is_unidirectional=False)
        # HTTP/3 gereği pseudo-header'lar:
        # :method, :scheme, :authority(host:port), :path
        headers = [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", parsed.netloc.encode()),
            (b":path", path.encode()),
        ]
        # Bu stream için HTTP/3 HEADERS frame'ini gönder.
        # end_stream=True => HEADERS ile birlikte isteğin bittiğini söyle (body yok).
        self._http.send_headers(stream_id, headers, end_stream=True)
        # Sunucudan gelecek HEADERS ve DATA event'lerini beklemek için _done event'inin set edilmesini bekle
        await self._done.wait()


async def main(url):
    """
    Komut satırından verilen URL için QUIC bağlantısını kur,
    HTTP/3 protokolü üzerinde GET isteği gönder.
    """
    # URL'yi parçala
    parsed = urlparse(url)
    # QUIC istemci konfigürasyonu oluştur.
    # is_client=True => bu tarafta istemci olduğumuzu söylüyoruz
    # alpn_protocols=H3_ALPN => ALPN üzerinden "h3" protokolü müzakere edilecek.
    conf = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN)
    # Sertifika doğrulamasını kapatıyoruz (self-signed sertifikada hata olmaması için).
    # Gerçek ortamda kesinlikle verify_mode=False kullanılmamalı.
    conf.verify_mode = False
    # aioquic.asyncio.connect ile QUIC/TLS bağlantısı kuruyoruz.
    # async with: bağlan, context'ten çıkarken otomatik olarak kapat.
    async with connect(
        parsed.hostname, parsed.port, configuration=conf, create_protocol=Http3Client
    ) as client:
        # QUIC/TLS handshake tamamlandıktan sonra buraya düşeriz
        print("Handshake tamam, GET gönderiliyor...")
        # client nesnesi bizim Http3Client sınıfımızdan bir örnek.
        # Üzerinde tanımlı get() metodunu çağırarak aslında HTTP/3 isteğimizi gönderiyoruz.
        await client.get(url)
        await client._done.wait()
        total_time = client.end_time - client.start_time
        print(f"HTTP/3 Toplam Süre: {total_time:.4f} saniye")

# Bu dosya direkt çalıştırıldıysa (import edilmediyse)
if __name__ == "__main__":
    # asyncio.run ile main coroutine'ini çalıştırıyoruz.
    # sys.argv[1] => komut satırında verilen URL
    asyncio.run(main(sys.argv[1]))
