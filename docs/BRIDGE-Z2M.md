# Most Home Assistant / Zigbee2MQTT ↔ Sinum (SinumBridge)

Celem mostu jest udostępnienie wybranych urządzeń z Home Assistant (np. Zigbee2MQTT, ESPHome, Z-Wave, Shelly) w ekosystemie Sinum w sposób dwukierunkowy i w czasie rzeczywistym, bez tworzenia pętli sprzężenia zwrotnego i bez modyfikowania konfiguracji źródłowej.

Most jest **wbudowanym, asynchronicznym komponentem integracji** (`custom_components/sinum_home_assistant/bridge.py`), działającym w cyklu życia Home Assistant (bez konieczności uruchamiania zewnętrznych skryptów czy usług systemd).

---

## Zasady działania i bezpieczeństwo

1. **Źródło odczytu**: Most subskrybuje wewnętrzną magistralę zdarzeń Home Assistant (`state_changed`). Nie ingeruje w konfigurację urządzeń Zigbee ani brokera MQTT.
2. **Kierunek dwukierunkowy w czasie rzeczywistym**:
   - **HA → Sinum**: Zmiana stanu encji w Home Assistant natychmiast wysyła polecenie REST/PATCH do wirtualnego urządzenia w chmurze Sinum.
   - **Sinum → HA**: Asynchroniczny klient WebSocket STOMP/SockJS subskrybuje kanał `/topic/<deviceId>`. Akcja użytkownika w aplikacji Sinum (suwak jasności, zmiana barwy, przełącznik) natychmiast wywołuje odpowiednią usługę w Home Assistant (`light.turn_on`, `switch.turn_on` itp.).
3. **Eliminacja pętli (Echo Suppression)**: Mechanizm tłumienia echa sprawdza ostatnio wysłane stany (`_ha_last`, `_recent`) i ignoruje zdarzenia zwrotne wynikające z własnych poleceń. Dla przekaźników (`relay`) obowiązuje dodatkowe okno 3 s (`RELAY_ECHO_SECONDS`) po zapisie HA → Sinum: asynchroniczne echo `ON`/`OFF` z Sinum bywa opóźnione i może dotrzeć już po powrocie przekaźnika do `OFF`, więc w tym oknie most tylko aktualizuje `_sinum_last` i nie wywołuje ponownie usługi w HA (ochrona impulsowych bram i ogrodzeń przed drugim impulsem).
4. **Izolacja encji w HA**: Wirtualne urządzenia tworzone w chmurze Sinum są oznaczane unikalnym znacznikiem `integration_uid: z2m-bridge`. Główny koordynator integracji odfiltrowuje je, dzięki czemu nie są one ponownie importowane do Home Assistant jako zdublowane encje.
5. **Dostępność (availability)**: Gdy encja w HA ma stan `unavailable` lub `unknown` (np. lampa Zigbee odcięta od prądu), most ustawia urządzenie w Sinum na status `offline` komendą `set_availability` (Lua `onCommand`). Po powrocie encji status wraca na `online`, a wartości są synchronizowane ponownie. Akcje z Sinum dla urządzenia `offline` są ignorowane. Nowe urządzenia dostają handler w Lua od razu; istniejące dostają go leniwie przy pierwszej utracie dostępności.

---

## Wybór urządzeń za pomocą etykiet

Wybór urządzeń i encji do mostu odbywa się deklaratywnie w Home Assistant:

1. Oznacz wybrane urządzenie lub encję etykietą **`sinumbridge`** (domyślna etykieta, z możliwością zmiany w opcjach integracji; etykieta legacy `sinum` jest również akceptowana).
2. Mapper odczytuje rejestr urządzeń i encji HA, filtruje encje wyłączone lub ukryte, a następnie automatycznie tworzy lub aktualizuje wirtualne urządzenia w chmurze Sinum.
3. Mapowanie jest utrwalane w magazynie Home Assistant (`.storage/sinum_home_assistant.bridge`), z możliwością jednorazowego importu z pliku `mapping.json`.

---

## Obsługiwane klasy urządzeń i warianty Sinum

| Klasa urządzenia w HA | Wariant wirtualny Sinum | Kontrolki i elementy UI Sinum | Obsługiwane funkcje i normalizacja |
|---|---|---|---|
| **Oświetlenie (`light`)** | `generic` | `color_picker` | Włącz/Wyłącz, jasność (0–100%), kolor RGB (HEX), temperatura barwowa (Kelvin). Sinum używa trybu `temperature`, a HA `color_temp`; most dokonuje automatycznej normalizacji. |
| **Kontaktrony / czujniki otwarcia** | `two_state_input_sensor` | `text` | Wyświetla `Otwarte` lub `Zamknięte`. Obsługuje odwrócenie logiki (`invert: true`). |
| **Bramy wjazdowe i garażowe** | `momentary` (custom) | `button` + `text` | Natywny przycisk `pulse_button` w Sinum wywołuje akcję HA (`script.*`, `input_button.*`, `cover.*`) — nigdy bezpośrednio przekaźnika. Tekst `contact_state` pokazuje kontaktron/pozycję (`Otwarta`/`Zamknięta`), a watchdog 3 s wymusza `off`, jeśli impuls nie został zwolniony. |
| **Temperatura** | `temperature_sensor` | `text` (tekst-default) | Wartość rejestrowana w formacie Sinum (×10) oraz formatowany ciąg tekstowy (np. `21.4 °C`). |
| **Wilgotność** | `humidity_sensor` | `text` (tekst-default) | Wartość w formacie Sinum (×10) oraz ciąg tekstowy (np. `52.0 %`). |
| **Wielkości analogowe (ciśnienie, napięcie itp.)** | `analog_input` | Wartość wariantu | Dowolna wartość numeryczna z przypisaną jednostką (`unit`). |
| **Pomiary energii i mocy** | `energy_meter` | Wartość wariantu | Pobór mocy (W) oraz zużycie energii (kWh). |
| **Poziom baterii** | `battery` | Wartość wariantu | Stan naładowania (0–100%). |
| **Klimatyzator (`climate`)** | `custom_device_module` | `variant: ac_module` | Tryby pracy (auto, chłodzenie, ogrzewanie, wentylacja, osuszanie), nastawa temperatury zadanej i odczyt temperatury pomieszczenia. |

### Wariant `momentary` (bramy i ogrodzenia)

Wpisy bram w pliku mapowania (`mapping.json` / `.storage/sinum_home_assistant.bridge`) używają wariantu `momentary`:

```json
"switch.garaz_agrestowa": {
  "id": 103,
  "variant": "momentary",
  "field": "state",
  "name": "HA · Garaż Agrestowa",
  "action_entity": "script.brama_puls_agrestowa",
  "state_entity": "binary_sensor.garaz_agrestowa_kontaktron_contact",
  "state_invert": false,
  "text_true": "Otwarta",
  "text_false": "Zamknięta",
  "pulse_text": "Impuls"
}
```

- `action_entity` — encja akcji w HA. Obsługiwane domeny: `script` (`turn_on`), `input_button`/`button` (`press`), `cover` (`toggle`); brak wpisu = fallback na `switch.turn_on` z automatycznym zwolnieniem po 0,5 s.
- `state_entity` — kontaktron lub encja pozycji. `state_invert: true` odwraca logikę (np. kontaktron „zamknięta”, gdzie `on` = zamknięta brama).
- `pulse_text` — etykieta przycisku w Sinum (domyślnie `Impuls`).
- `watch_entity` — opcjonalny przekaźnik pilnowany przez watchdog (domyślnie encja mapowana, jeśli jest `switch`/`light`/`input_boolean`).
- Brak `state_entity` (np. ogrodzenia bez kontaktronu) pokazuje `Brak czujnika`.
- Ponowna akcja w ciągu 1 s jest ignorowana (debounce), a watchdog po 3 s wyłącza przekaźnik, jeśli nadal jest `on`.
- Migracja istniejących urządzeń relay → momentary odbywa się przez zmianę wpisu w `mapping.json`; most przebudowuje elementy urządzenia przy najbliższej rekoncyliacji (bez usuwania urządzenia i bez zmiany jego ID).

---

## Statystyki i wykresy InfluxDB w Sinum

Domyślnie chmura Sinum nie rejestruje punktów statystycznych dla wirtualnych urządzeń niestandardowych. Aby wartości z mostu były widoczne na wykresach historycznych w aplikacji Sinum, most wstrzykuje odpowiedni blok skryptu Lua:

```lua
function CustomDevice:onEvent(event)
  self:setValue("status", "online")
  if self:changedVariantDeviceValue("temperature") then
    statistics:addPoint("temperature", self:getVariantDeviceValue("temperature"), unit.celsius_x10)
  end
end
```

Dzięki temu punkty pomiarowe trafiają do bazy InfluxDB w chmurze Sinum i mogą być prezentowane na wykresach po skonfigurowaniu zapytania statystycznego w aplikacji.

---

## Pomiary wydajności i czasy reakcji (Push vs Polling)

Dzięki zastosowaniu protokołu WebSocket STOMP/SockJS opóźnienia w komunikacji dwukierunkowej zostały zredukowane do ułamków sekundy:

- **Brama / impuls**: ~0.45 s
- **Zmiana stanu i jasności światła**: ~0.60–0.90 s
- **Czujnik temperatury i wilgotności**: ~0.45–0.65 s
- **Aktualizacja stanu kontaktronu**: ~1.50–1.80 s
- **Zmiana dostępności (online/offline)**: < 1 s

Tradycyjne odpytywanie chmury (polling) zostało zachowane wyłącznie jako proces rekoncyliacji (co 60 s), zapewniający spójność stanów po ewentualnym zerwaniu połączenia internetowego.

---

## Znane ograniczenia techniczne

- **Brak wirtualnego wariantu dla rolet**: Chmurowe API Sinum nie udostępnia typu `cover` dla urządzeń wirtualnych.
- **Kamery RTSP / NVR**: Chmura Sinum odrzuca rejestrację strumieni kamer bez fizycznego rejestratora sprzętowego TECH (`422 NvrDeviceNotFound`).
- **Status custom sensorów**: Wirtualne czujniki w interfejsie Sinum raportują status `unknown`, pomimo że przekazywane wartości i elementy UI działają poprawnie.
- **Relay zarządzany przez termostat**: Przekaźnik przypisany do termostatu wirtualnego nie generuje własnych punktów statystycznych relay w chmurze.
