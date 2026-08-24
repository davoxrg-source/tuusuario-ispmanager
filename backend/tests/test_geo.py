from app.services.geo import haversine_km


def test_haversine_known_distance_tulua_palmira():
    # Tuluá (4.0847, -76.1954) a Palmira (3.5322, -76.3033) -- distancia
    # real en línea recta ronda los 65 km.
    km = haversine_km(4.0847, -76.1954, 3.5322, -76.3033)
    assert 60 < km < 70


def test_haversine_same_point_is_zero():
    assert haversine_km(4.0, -76.0, 4.0, -76.0) == 0


def test_haversine_symmetric():
    a_to_b = haversine_km(4.0847, -76.1954, 3.5322, -76.3033)
    b_to_a = haversine_km(3.5322, -76.3033, 4.0847, -76.1954)
    assert round(a_to_b, 6) == round(b_to_a, 6)
