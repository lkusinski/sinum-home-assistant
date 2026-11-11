# Bridge HA / Zigbee2MQTT → Sinum — plan

Cel: pokazać wybrane urządzenia z produkcyjnego HA (Zigbee2MQTT) w Sinum,
w pokoju **LAB Lukasz**, bez modyfikowania produkcyjnego HA.

## Bezpieczeństwo

- Źródło: **tylko odczyt** MQTT `zigbee2mqtt/#` z brokera produkcyjnego.
- Nie tworzymy encji, automatyzacji ani integracji w produkcyjnym HA.
- Opcjonalne `zigbee2mqtt/<friendly_name>/get` służy tylko do pobrania bieżącego
  stanu; nie zmienia urządzenia.
- Sinum: wyłącznie pokój testowy **LAB Lukasz** (id 11) i wirtualne urządzenia.

## Wybór urządzeń

Wariant docelowy: etykieta **`sinum`** w HA (device/entity label).
Bridge czyta rejestr przez read-only token HA.

Wariant startowy bez tokena: allowlista `friendly_name` w konfiguracji bridge’a
lub prefiks `sinum_` w nazwie Z2M. Pozwala przetestować most bez zmian w prod HA.

## Sprawdzone warianty Sinum

`POST /proxy/devices/virtual` przyjmuje `variant`:

- `temperature_sensor` — temperatura, ×10;
- `humidity_sensor` — wilgotność, ×10;
- `analog_input` — dowolna wartość liczbowa + `unit`;
- `energy_meter` — moc, energia;
- `battery` — SOC;
- `relay` — on/off;
- `two_state_input_sensor` — kontakt/ruch;
- `temperature_regulator`;
- `heat_pump`, `inverter`, `common_dhw_main`, `car_charger`;
- `generic` — własne elementy (switcher, slider, text, color picker itd.).

Testy PATCH potwierdziły aktualizację `variant_device` dla temperatury,
wilgotności, analog input, relay, two-state, energy meter i battery.
Wariant **`light` nie jest akceptowany** — światła trzeba na razie mapować jako
`relay` (on/off) albo `generic` z elementami (jasność/kolor).

## Mapowanie klas

| HA / Z2M | Sinum variant |
|---|---|
| temperature | `temperature_sensor` |
| humidity | `humidity_sensor` |
| pressure, illuminance, voltage, current, linkquality, battery % | `analog_input` |
| power / energy | `energy_meter` |
| switch, plug, light (on/off) | `relay` |
| contact, motion, battery_low | `two_state_input_sensor` |
| climate / TRV | `temperature_regulator` (do walidacji) |
| action/button | `generic` elementy (później) |
| light brightness/color, cover | brak natywnego wariantu — `generic` lub pominięte |

## Architektura

1. **Mapper** — czyta `zigbee2mqtt/bridge/devices`, wybiera urządzenia, tworzy
   wirtualne urządzenia w Sinum i zapisuje mapowanie (JSON/SQLite).
2. **Worker** — subskrybuje tematy stanu Z2M i PATCH-uje odpowiadające pola Sinum
   (z debounce/rate limit).
3. **Back-channel** — opcjonalnie później: odczyt Sinum i publikacja komend do
   Z2M (dwukierunkowe sterowanie).
4. Uruchomienie: usługa na B7/CT310; konfiguracja poza produkcyjnym HA.

## Ograniczenia

- Brak natywnego `light`/`cover` w wirtualnych urządzeniach Sinum.
- Grupy Z2M, bridge, repeater i diagnostyka (`linkquality`, battery_low) nie
  powinny być osobnymi urządzeniami w Sinum; można je pominąć.
- Tag `#sinum` wymaga read-only tokena HA albo allowlisty w bridge’u.
