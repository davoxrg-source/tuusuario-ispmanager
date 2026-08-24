import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.hotspot import (
    create_hotspot_profile,
    delete_hotspot_profile,
    generate_voucher_batch,
    list_hotspot_profiles,
    list_hotspot_vouchers,
    sell_voucher,
    update_hotspot_profile,
    void_voucher,
)
from app.models.hotspot import HotspotProfile, HotspotVoucherStatus
from app.models.user import User, UserRole
from app.schemas.hotspot import (
    HotspotProfileCreate,
    HotspotProfileUpdate,
    HotspotVoucherBatchCreate,
)
from app.services.hotspot.vouchers import create_voucher_batch, generate_voucher_code


def _make_user(db_session, name="Staff", role=UserRole.TECHNICIAN) -> User:
    user = User(
        full_name=name, email=f"{uuid.uuid4()}@compusoft-isp.com", hashed_password="x", role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_profile(db_session, **overrides) -> HotspotProfile:
    profile = HotspotProfile(name=f"Perfil {uuid.uuid4()}", duration_hours=24, price=5000, currency="COP")
    for field, value in overrides.items():
        setattr(profile, field, value)
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def test_profile_crud(db_session):
    profile = create_hotspot_profile(
        HotspotProfileCreate(name="24 horas", duration_hours=24, price=5000, currency="COP"), db_session
    )
    assert profile.name == "24 horas"

    updated = update_hotspot_profile(profile.id, HotspotProfileUpdate(price=6000), db_session)
    assert updated.price == 6000

    profiles = list_hotspot_profiles(db_session)
    assert profile.id in {p.id for p in profiles}

    delete_hotspot_profile(profile.id, db_session)
    assert list_hotspot_profiles(db_session) == []


def test_profile_requires_duration_or_data_limit(db_session):
    with pytest.raises(HTTPException) as exc:
        create_hotspot_profile(HotspotProfileCreate(name="Vacío", price=1000), db_session)
    assert exc.value.status_code == 400

    profile = _make_profile(db_session)
    with pytest.raises(HTTPException) as exc:
        update_hotspot_profile(
            profile.id, HotspotProfileUpdate(duration_hours=None, data_limit_mb=None), db_session
        )
    assert exc.value.status_code == 400


def test_profile_with_data_limit_only_is_valid(db_session):
    profile = create_hotspot_profile(
        HotspotProfileCreate(name="2GB", data_limit_mb=2000, price=3000, currency="COP"), db_session
    )
    assert profile.data_limit_mb == 2000
    assert profile.duration_hours is None


def test_delete_profile_with_vouchers_fails(db_session):
    profile = _make_profile(db_session)
    create_voucher_batch(db_session, profile, 1)
    with pytest.raises(HTTPException) as exc:
        delete_hotspot_profile(profile.id, db_session)
    assert exc.value.status_code == 400


def test_create_voucher_batch_generates_unique_codes_with_frozen_price(db_session):
    profile = _make_profile(db_session, price=4500)
    vouchers = create_voucher_batch(db_session, profile, 10)
    assert len(vouchers) == 10
    codes = {v.code for v in vouchers}
    assert len(codes) == 10
    batch_ids = {v.batch_id for v in vouchers}
    assert len(batch_ids) == 1
    assert all(v.price == 4500 for v in vouchers)
    assert all(v.status == HotspotVoucherStatus.UNUSED for v in vouchers)


def test_generate_voucher_code_uses_safe_alphabet():
    code = generate_voucher_code()
    assert len(code) == 8
    for char in "0O1IL":
        assert char not in code


def test_generate_voucher_batch_route_quantity_bounds(db_session):
    profile = _make_profile(db_session)
    with pytest.raises(HTTPException) as exc:
        generate_voucher_batch(HotspotVoucherBatchCreate(profile_id=profile.id, quantity=0), db_session)
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        generate_voucher_batch(HotspotVoucherBatchCreate(profile_id=profile.id, quantity=501), db_session)
    assert exc.value.status_code == 400

    vouchers = generate_voucher_batch(
        HotspotVoucherBatchCreate(profile_id=profile.id, quantity=3), db_session
    )
    assert len(vouchers) == 3


def test_sell_voucher(db_session):
    profile = _make_profile(db_session)
    staff = _make_user(db_session)
    [voucher] = create_voucher_batch(db_session, profile, 1)

    sold = sell_voucher(voucher.id, db_session, staff)
    assert sold.status == HotspotVoucherStatus.SOLD
    assert sold.sold_by_user_id == staff.id
    assert sold.sold_at is not None

    with pytest.raises(HTTPException) as exc:
        sell_voucher(voucher.id, db_session, staff)
    assert exc.value.status_code == 400


def test_void_voucher_from_unused_and_sold(db_session):
    profile = _make_profile(db_session)
    staff = _make_user(db_session)
    vouchers = create_voucher_batch(db_session, profile, 2)

    voided_unused = void_voucher(vouchers[0].id, db_session)
    assert voided_unused.status == HotspotVoucherStatus.VOID
    assert voided_unused.voided_at is not None

    sold = sell_voucher(vouchers[1].id, db_session, staff)
    voided_sold = void_voucher(sold.id, db_session)
    assert voided_sold.status == HotspotVoucherStatus.VOID


def test_void_voucher_already_void_rejected(db_session):
    profile = _make_profile(db_session)
    [voucher] = create_voucher_batch(db_session, profile, 1)
    void_voucher(voucher.id, db_session)
    with pytest.raises(HTTPException) as exc:
        void_voucher(voucher.id, db_session)
    assert exc.value.status_code == 400


def test_list_hotspot_vouchers_filters(db_session):
    profile_a = _make_profile(db_session, name="A")
    profile_b = _make_profile(db_session, name="B")
    create_voucher_batch(db_session, profile_a, 2)
    [voucher_b] = create_voucher_batch(db_session, profile_b, 1)

    only_b = list_hotspot_vouchers(profile_id=profile_b.id, status_filter=None, batch_id=None, db=db_session)
    assert {v.id for v in only_b} == {voucher_b.id}

    by_batch = list_hotspot_vouchers(profile_id=None, status_filter=None, batch_id=voucher_b.batch_id, db=db_session)
    assert {v.id for v in by_batch} == {voucher_b.id}
