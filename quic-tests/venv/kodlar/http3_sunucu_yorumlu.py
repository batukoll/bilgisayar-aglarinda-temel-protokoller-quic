# 502531001 Batuhan KOL
# 502531012 Damla SOYDAN

import asyncio  # Asenkron işlemler ve event loop yönetimi için
import os  # Dosya yolu oluşturma, dosya var mı kontrolü gibi işlemler için
import logging  # Log çıktıları için

# aioquic içinde hazır gelen QUIC sunucu helper'ı
from aioquic.asyncio.server import serve
from aioquic.asyncio import QuicConnectionProtocol  # QUIC protokol taban sınıfı
from aioquic.quic.configuration import QuicConfiguration  # QUIC yapılandırma sınıfı
from aioquic.h3.connection import (
    H3Connection,
    H3_ALPN,
)  # HTTP/3 bağlantısı ve ALPN sabitleri
from aioquic.h3.events import HeadersReceived  # HTTP/3 HEADERS event tipi

# Log seviyesini DEBUG yaparak QUIC/HTTP3 ile ilgili debug mesajlarını görebiliyoruz
logging.basicConfig(level=logging.DEBUG)

# Statik dosyaların servis edileceği klasör
# Örn: ./www/index.html gibi
WWW_ROOT = "./www"


class HttpServerH3(QuicConnectionProtocol):
    """
    HTTP/3 sunucusu için protokol sınıfı.
    QUIC bağlantısı üzerinde HTTP/3 request/response işini yönetiyor.
    """

    def __init__(self, *args, **kwargs):
        # Üst sınıf kurucusu (QUIC tarafının temel kurulumları)
        super().__init__(*args, **kwargs)
        # HTTP/3 bağlantı nesnesi. self._quic: QuicConnection objesi
        self._http = H3Connection(self._quic)

    def quic_event_received(self, event):
        """
        QUIC tarafında bir event oluşunca aioquic bu metodu çağırır.
        Buradaki event, H3Connection'a verilir, o da HTTP/3 event'lerine çevirir.
        """
        # Gelen QUIC event'ini HTTP/3 event'lerine dönüştürüyoruz.
        for http_event in self._http.handle_event(event):
            # Eğer event, HTTP/3 HEADERS içeren bir request ise (istemciden gelen istek başlıkları)
            if isinstance(http_event, HeadersReceived):
                # Varsayılan path "/"
                path = "/"
                for k, v in http_event.headers:
                    # Gelen başlıkların içinde :path pseudo-header'ını arıyoruz
                    if k == b":path":
                        # :path header'ının değeri (örn: "/index.html")
                        path = v.decode()
                # Eğer path "/" ise, otomatik olarak "/index.html" gösterelim
                if path == "/":
                    path = "/index.html"
                # İstenen dosyanın gerçek dosya sistemindeki tam yolu
                # WWW_ROOT + istenen path (başındaki "/" kaldırılarak)
                full = os.path.join(WWW_ROOT, path.lstrip("/"))
                # Dosya yoksa 404 hatası dön
                if not os.path.exists(full):
                    self.send_error(http_event.stream_id, 404)
                    return
                # Dosyayı binary olarak okuyalım
                with open(full, "rb") as f:
                    body = f.read()
                # HTTP/3 yanıt başlıkları:
                # :status => HTTP durum kodu, content-type => MIME tipi
                headers = [
                    (b":status", b"200"),
                    (b"content-type", b"text/html"),
                ]
                # HEADERS frame'ini gönderiyoruz (stream ID: request'in stream'i)
                self._http.send_headers(http_event.stream_id, headers)
                # BODY'yi DATA frame olarak gönderiyoruz
                # end_stream=True => bu stream için veri gönderimi tamamlandı
                self._http.send_data(http_event.stream_id, body, end_stream=True)

    def send_error(self, stream_id, code):
        """
        Basit bir hata (ör: 404) yanıtı göndermek için yardımcı fonksiyon.
        """
        # Hata durum başlıkları
        headers = [
            (b":status", str(code).encode()),
            (b"content-type", b"text/plain"),
        ]
        # Gövde içeriği: "Error 404" gibi
        body = f"Error {code}".encode()
        # HEADERS + DATA olarak hatayı gönder
        self._http.send_headers(stream_id, headers)
        self._http.send_data(stream_id, body, end_stream=True)


async def main():
    """
    HTTP/3 sunucusunu 127.0.0.1:4433 adresinde ayağa kaldırır,
    QUIC/HTTP3 konfigürasyonunu yapar ve sonsuza kadar çalışır.
    """
    # QUIC konfigürasyonu: sunucu modunda (is_client=False)
    # alpn_protocols=H3_ALPN => ALPN üzerinden HTTP/3 ("h3") protokolü müzakere edilecek
    conf = QuicConfiguration(is_client=False, alpn_protocols=H3_ALPN)
    # TLS için sunucu sertifikası ve özel anahtarı yüklüyoruz.
    # "server.crt" ve "server.key" dosyalarının aynı klasörde olması gerekiyor.
    conf.load_cert_chain("server.crt", "server.key")
    # aioquic.asyncio.server.serve fonksiyonu QUIC sunucusunu başlatır.
    # host="127.0.0.1", port=4433 üzerinde dinlemeye başlar.
    # create_protocol=HttpServerH3 => Her yeni bağlantı için HttpServerH3 sınıfından bir örnek oluşturulacak.
    await serve(
        host="127.0.0.1", port=4433, configuration=conf, create_protocol=HttpServerH3
    )
    # Buraya kadar gelindiyse sunucu ayağa kalkmıştır.
    print("HTTP/3 sunucusu çalışıyor: https://127.0.0.1:4433/")
    # Sunucunun sonsuza kadar çalışmasını sağlamak için hiç set edilmeyecek bir Event bekleniyor.
    # Böylece main() coroutine'i bitmiyor, program da kapanmıyor.
    await asyncio.Event().wait()


# Dosya direkt çalıştırıldığında (import edilmediğinde) sunucuyu başlat
if __name__ == "__main__":
    # asyncio.run ile main coroutine'ini başlatıyoruz.
    asyncio.run(main())
