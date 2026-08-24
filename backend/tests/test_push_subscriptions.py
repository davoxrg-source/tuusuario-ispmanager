from app.api.routes.portal import create_push_subscription, delete_push_subscription, get_vapid_public_key
from app.models.client import Client, ClientStatus
from app.models.push_subscription import PushSubscription
from app.schemas.notification import PushSubscriptionCreate, PushSubscriptionKeys


def _make_client(db_session, **overrides) -> Client:
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, ip_address=None)
    for field, value in overrides.items():
        setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def test_create_push_subscription_persists_it(db_session):
    client = _make_client(db_session)
    payload = PushSubscriptionCreate(
        endpoint="https://push.example/abc", keys=PushSubscriptionKeys(p256dh="k", auth="a")
    )

    create_push_subscription(payload, db_session, client)

    subs = db_session.query(PushSubscription).filter(PushSubscription.client_id == client.id).all()
    assert len(subs) == 1
    assert subs[0].endpoint == "https://push.example/abc"


def test_create_push_subscription_upserts_by_endpoint(db_session):
    client_a = _make_client(db_session)
    client_b = _make_client(db_session)
    payload = PushSubscriptionCreate(
        endpoint="https://push.example/shared", keys=PushSubscriptionKeys(p256dh="k1", auth="a1")
    )
    create_push_subscription(payload, db_session, client_a)

    updated_payload = PushSubscriptionCreate(
        endpoint="https://push.example/shared", keys=PushSubscriptionKeys(p256dh="k2", auth="a2")
    )
    create_push_subscription(updated_payload, db_session, client_b)

    subs = db_session.query(PushSubscription).filter(PushSubscription.endpoint == "https://push.example/shared").all()
    assert len(subs) == 1
    assert subs[0].client_id == client_b.id
    assert subs[0].p256dh == "k2"


def test_delete_push_subscription_scoped_to_own_client(db_session):
    client_a = _make_client(db_session)
    client_b = _make_client(db_session)
    create_push_subscription(
        PushSubscriptionCreate(endpoint="https://push.example/x", keys=PushSubscriptionKeys(p256dh="k", auth="a")),
        db_session,
        client_a,
    )

    # client_b intenta borrar la suscripción de client_a -- no hace nada
    delete_push_subscription("https://push.example/x", db_session, client_b)
    assert db_session.query(PushSubscription).filter(PushSubscription.client_id == client_a.id).count() == 1

    delete_push_subscription("https://push.example/x", db_session, client_a)
    assert db_session.query(PushSubscription).filter(PushSubscription.client_id == client_a.id).count() == 0


def test_vapid_public_key_returns_configured_value():
    result = get_vapid_public_key()
    assert isinstance(result.public_key, str)
