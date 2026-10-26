from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import count
import json
from queue import Queue
import ssl
from threading import Thread
from types import SimpleNamespace

import certifi
import pytest
import trustme
from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve

from signalfx.signalflow import SignalFlowClient
from signalfx.signalflow.sse import SSETransport


@pytest.fixture
def certificate_authority(tmp_path, monkeypatch):
    authority = trustme.CA()
    bundle = tmp_path / "ca.pem"
    authority.cert_pem.write_to_path(bundle)
    monkeypatch.setattr(certifi, "where", lambda: str(bundle))
    return authority, bundle


@pytest.fixture
def fake_signalflow_server():
    @contextmanager
    def start_server(certificate, *, disconnect_first=False):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        certificate.configure_cert(context)
        received = Queue()
        connections = count()

        def handle_connection(connection):
            connection_number = next(connections)
            try:
                received.put(json.loads(connection.recv(timeout=5)))
                connection.send(json.dumps({"type": "authenticated"}))
                for raw_request in connection:
                    request = json.loads(raw_request)
                    received.put(request)
                    if disconnect_first and connection_number == 0:
                        connection.close(code=1012)
                        return
                    connection.send(
                        json.dumps(
                            {
                                "type": "control-message",
                                "channel": request["channel"],
                                "event": "JOB_START",
                                "timestampMs": 0,
                                "handle": "test-computation",
                            }
                        )
                    )
                    connection.send(
                        json.dumps(
                            {
                                "type": "control-message",
                                "channel": request["channel"],
                                "event": "END_OF_CHANNEL",
                                "timestampMs": 0,
                            }
                        )
                    )
            except ConnectionClosed:
                pass

        with serve(
            handle_connection,
            "127.0.0.1",
            0,
            ssl=context,
            compression=None,
            close_timeout=1,
        ) as server:
            thread = Thread(target=server.serve_forever)
            thread.start()
            try:
                yield SimpleNamespace(
                    endpoint=f"https://127.0.0.1:{server.socket.getsockname()[1]}",
                    received=received,
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                assert not thread.is_alive()

    return start_server


def test_trusted_peer_receives_token_and_runs_computation(
    certificate_authority, fake_signalflow_server
):
    authority, _ = certificate_authority
    with fake_signalflow_server(authority.issue_cert("127.0.0.1")) as server:
        with SignalFlowClient(token="test-token", endpoint=server.endpoint) as client:
            computation = client.execute("data('test').publish()")
            assert [message.handle for message in computation.stream()] == [
                "test-computation"
            ]
        authentication = server.received.get(timeout=5)
        assert authentication["type"] == "authenticate"
        assert authentication["token"] == "test-token"
        assert server.received.get(timeout=5)["type"] == "execute"


@pytest.mark.parametrize(
    "certificate_error",
    ["self-signed", "untrusted", "hostname", "expired", "not-yet-valid"],
)
def test_invalid_peer_never_receives_token(
    certificate_error, certificate_authority, fake_signalflow_server
):
    authority, _ = certificate_authority
    hostname = "127.0.0.1"
    validity = {}
    now = datetime.now(timezone.utc)
    if certificate_error == "untrusted":
        authority = trustme.CA()
    elif certificate_error == "hostname":
        hostname = "wrong-host.example"
    elif certificate_error == "expired":
        validity = {
            "not_before": now - timedelta(days=2),
            "not_after": now - timedelta(days=1),
        }
    elif certificate_error == "not-yet-valid":
        validity = {
            "not_before": now + timedelta(days=1),
            "not_after": now + timedelta(days=2),
        }

    if certificate_error == "self-signed":
        self_signed = trustme.CA()
        certificate = trustme.LeafCert(
            private_key_pem=self_signed.private_key_pem.bytes(),
            server_cert_pem=self_signed.cert_pem.bytes(),
            chain_to_ca=[],
        )
    else:
        certificate = authority.issue_cert(hostname, **validity)

    with fake_signalflow_server(certificate) as server:
        with SignalFlowClient(token="test-token", endpoint=server.endpoint) as client:
            with pytest.raises(ssl.SSLCertVerificationError):
                client.execute("data('test').publish()")
        assert server.received.empty()


def test_custom_ca_bundle_authenticates_private_peer(tmp_path, fake_signalflow_server):
    authority = trustme.CA()
    bundle = tmp_path / "private-ca.pem"
    authority.cert_pem.write_to_path(bundle)
    with fake_signalflow_server(authority.issue_cert("127.0.0.1")) as server:
        with SignalFlowClient(
            token="test-token", endpoint=server.endpoint, ca_certs=bundle
        ) as client:
            computation = client.execute("data('test').publish()")
            assert [message.handle for message in computation.stream()] == [
                "test-computation"
            ]
        assert server.received.get(timeout=5)["token"] == "test-token"


@pytest.mark.parametrize("bundle_error", ["missing", "invalid"])
def test_unusable_custom_ca_bundle_never_falls_back(
    bundle_error, certificate_authority, fake_signalflow_server, tmp_path
):
    authority, _ = certificate_authority
    bundle = tmp_path / "unusable-ca.pem"
    if bundle_error == "invalid":
        bundle.write_text("invalid CA bundle")
    with fake_signalflow_server(authority.issue_cert("127.0.0.1")) as server:
        with SignalFlowClient(
            token="test-token", endpoint=server.endpoint, ca_certs=bundle
        ) as client:
            with pytest.raises((FileNotFoundError, ssl.SSLError)):
                client.execute("data('test').publish()")
        assert server.received.empty()


@pytest.mark.parametrize("endpoint", ["http://localhost", "ws://localhost"])
def test_plaintext_websocket_endpoint_is_rejected(endpoint):
    with pytest.raises(ValueError, match="https:// or wss://"):
        SignalFlowClient(token="test-token", endpoint=endpoint)


def test_existing_custom_transport_factory_accepts_default_client_options():
    def fake_transport(token, endpoint, timeout, compress, proxy_url):
        return SimpleNamespace(close=lambda: None)

    with SignalFlowClient(token="test-token", transport=fake_transport):
        pass


def test_sse_transport_accepts_custom_ca_bundle(tmp_path):
    authority = trustme.CA()
    bundle = tmp_path / "private-ca.pem"
    authority.cert_pem.write_to_path(bundle)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    authority.issue_cert("127.0.0.1").configure_cert(context)
    received_tokens = Queue()

    class FakeSignalFlowHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            received_tokens.put(self.headers["X-SF-Token"])
            self.rfile.read(int(self.headers["Content-Length"]))
            body = (
                b"event: control-message\n"
                b'data: {"event": "END_OF_CHANNEL", "timestampMs": 0}\n\n'
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), FakeSignalFlowHandler) as server:
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            with SignalFlowClient(
                token="test-token",
                endpoint=f"https://127.0.0.1:{server.server_port}",
                transport=SSETransport,
                ca_certs=bundle,
            ) as client:
                assert list(client.execute("data('test').publish()").stream()) == []
            assert received_tokens.get(timeout=5) == "test-token"
        finally:
            server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


@pytest.mark.parametrize("remove_trust", [False, True])
def test_reconnect_validates_current_ca_bundle_before_sending_token(
    remove_trust, certificate_authority, fake_signalflow_server
):
    authority, bundle = certificate_authority
    certificate = authority.create_child_ca().issue_cert("127.0.0.1")
    with fake_signalflow_server(certificate, disconnect_first=True) as server:
        with SignalFlowClient(token="test-token", endpoint=server.endpoint) as client:
            computation = client.execute("data('test').publish()")
            assert server.received.get(timeout=5)["token"] == "test-token"
            assert server.received.get(timeout=5)["type"] == "execute"
            if remove_trust:
                trustme.CA().cert_pem.write_to_path(bundle)
                with pytest.raises(ssl.SSLCertVerificationError):
                    list(computation.stream())
                assert server.received.empty()
            else:
                assert [message.handle for message in computation.stream()] == [
                    "test-computation"
                ]
                assert server.received.get(timeout=5)["token"] == "test-token"
                assert server.received.get(timeout=5)["type"] == "execute"
