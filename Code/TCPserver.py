import socket
import requests
import mimetypes
from urllib.parse import urlparse
from pathlib import Path

# Define additional file types
mimetypes.types_map['.pdf'] = 'application/pdf'
mimetypes.types_map['.zip'] = 'application/zip'
mimetypes.types_map['.docx'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
mimetypes.types_map['.jpg'] = 'image/jpeg'
mimetypes.types_map['.jpeg'] = 'image/jpeg'
mimetypes.types_map['.png'] = 'image/png'
mimetypes.types_map['.gif'] = 'image/gif'
mimetypes.types_map['.bmp'] = 'image/bmp'
mimetypes.types_map['.doc'] = 'application/msword'
mimetypes.types_map['.txt'] = 'text/plain'
mimetypes.types_map['.csv'] = 'text/csv'
mimetypes.types_map['.mp3'] = 'audio/mpeg'
mimetypes.types_map['.wav'] = 'audio/wav'
mimetypes.types_map['.avi'] = 'video/x-msvideo'
mimetypes.types_map['.mp4'] = 'video/mp4'
mimetypes.types_map['.mkv'] = 'video/x-matroska'


def download_file(url, filename):
    parsed_url = urlparse(url)

    if not all([parsed_url.scheme, parsed_url.netloc]):
        return 'Please enter a valid URL'

    try:
        response = requests.get(url, stream=True)
        content_type = response.headers.get('Content-Type')

        extension = mimetypes.guess_extension(content_type)
        filename = filename

        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()

        return f'Download complete. File saved as {filename}.'
    except requests.exceptions.RequestException as e:
        return f'Error: {e}'


serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print("Server listening... ")

host = socket.gethostname()

tcp_port = 9898

serversocket.bind((host, tcp_port))

serversocket.listen(1)

while True:
    clientsocket, addr = serversocket.accept()

    print("Got a connection from %s" % str(addr))

    data = clientsocket.recv(1024)
    url, filename = data.decode('utf-8').split(',')

    content_type = requests.head(url).headers.get('Content-Type')
    if not content_type:
        response = 'Error: URL did not return a Content-Type header'
    else:
        extension = mimetypes.guess_extension(content_type)
        if not extension:
            response = f'Error: unsupported content type {content_type}'
        else:
            filename = filename + extension if extension else filename
            if Path(filename).exists():
                response = f'File {filename} already exists on the server.'
            else:
                response = download_file(url, filename)

    # send response to client
    clientsocket.send(response.encode('utf-8'))

    clientsocket.close()
