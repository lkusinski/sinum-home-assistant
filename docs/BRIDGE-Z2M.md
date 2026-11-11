# Bridge HA / Zigbee2MQTT → Sinum — plan

Cel: pokazać wybrane urządzenia z produkcyjnego HA (Zigbee2MQTT) w Sinum,
w pokojach **LAB Lukasz** (11) i **LAB Działające** (12), bez modyfikowania
produkcyjnego HA.

## Bezpieczeństwo

- Źródło: **tylko odczyt** MQTT `zigbee2mqtt/#` z brokera produkcyjnego.
- Nie tworzymy encji, automatyzacji ani integracji w produkcyjnym HA.
- Opcjonalne `zigbee2mqtt/<friendly_name>/get` służy tylko do pobrania bieżącego
  stanu; nie zmienia urządzenia.
- Sinum: wyłącznie prywatne pokoje **LAB Lukasz** (id 11) i
  **LAB Działające** (id 12) oraz wirtualne urządzenia.

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
Wariant **`light` nie jest akceptowany** — światła są mapowane jako `generic`
z elementem `color_picker` (`set_state`, `set_brightness`, `set_color`,
`set_temperature`). Działa on/off, jasność, RGB i temperatura barwowa.
Czujniki temperatury/wilgotności wymagają dodatkowego elementu `text`, bo UI
Sinum nie pokazuje samodzielnie wartości wariantu sensor; most aktualizuje ten
element komendą `set_value` (np. `21.1 °C`, `52.6 %`). Przekaźniki dostają
element `switcher` (`switch-default`), a kontaktrony element `text`
(`contact_state`, `Otwarte`/`Zamknięte`). Most czyta stan elementu
przekaźnika i przy zmianie wykonuje akcję w HA oraz synchronizuje
`variant_device`.

Uwaga: `switch.garaz_agrestowa` to wyjście impulsowe — każde `turn_on`
przełącza bramę (otwórz/zamknij), a `turn_off` tylko zwalnia przekaźnik.
Zamknięcie bramy wymaga drugiego impulsu, nie wyłączenia przełącznika.

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

1. **Mapper** — czyta rejestr HA, wybiera urządzenia z etykietą `sinum`, tworzy
   wirtualne urządzenia w Sinum i zapisuje mapowanie (JSON).
2. **Push worker** (`event_worker.py`) — dwa strumienie zdarzeń:
   - HA WebSocket `state_changed` → natychmiastowy PATCH Sinum;
   - Sinum STOMP/SockJS `/topic/<deviceId>` → natychmiastowa akcja w HA.
   Echo jest tłumione znacznikiem czasu (`SUPPRESS`).
3. **Reconciliation** (`z2m_to_sinum.py`) — pełny przebieg co 300 s jako
   fallback i do naprawy rozjazdów.
4. Uruchomienie: `sinum-z2m.service` (reconciliation) i
   `sinum-z2m-events.service` (push) na CT310; konfiguracja poza produkcyjnym HA.

## Pomiary push

Na wirtualnej ławce **LAB Wirtualne** (pokój 13): brama ~0,45 s, lampa
~0,6–0,9 s, temperatura/wilgotność ~0,45–0,65 s, kontaktron ~1,8 s (aktualizacja
tekstu po zmianie stanu). Wcześniejszy polling 30 s nie jest potrzebny do
reakcji UI → HA; pozostał tylko jako 300-sekundowy fallback.

Stan realny: 91 endpointów, dwa światła E27 i sześć czujników
temperatury/wilgotności w **LAB Działające**; pozostałe w **LAB Lukasz**.
Wirtualna ławka: brama, lampa, kontaktron, temperatura i wilgotność w
**LAB Wirtualne** (13), oparte na lokalnych helperach B7
(`input_boolean.sinum_lab_*`, `input_number.sinum_lab_*`, `light.sinum_lab_lampa`).
Nie używamy produkcyjnego discovery MQTT — fałszywe urządzenia nie trafiają do
produkcyjnego HA.

## Symulacja klimatyzatora

Sinum nie ma wirtualnego typu AC; w LAB Wirtualne działa `generic` (141) z
elementami `power`/`mode`/`target`/`room_temp`. HA ma `climate.sinum_lab_klimatyzator`
na helperach (`input_boolean`, `input_number`, `input_select`). Most obsługuje
`variant: ac` w obie strony: zmiana w HA ustawia elementy Sinum, a zdarzenia
elementów Sinum aktualizują helpery HA. Test: ~0,4 s w obie strony.

## Ograniczenia

- Brak natywnego `light`/`cover` w wirtualnych urządzeniach Sinum.
- Grupy Z2M, bridge, repeater i diagnostyka (`linkquality`, battery_low) nie
  powinny być osobnymi urządzeniami w Sinum; można je pominąć.
- Tag `#sinum` wymaga read-only tokena HA albo allowlisty w bridge’u.
