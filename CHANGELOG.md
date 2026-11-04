# Changelog

Wydania tworzy automatycznie workflow `.github/workflows/release.yml` po zmianie `version` w `manifest.json` na gałęzi `main`. Opis wydania to sekcja `## <wersja>` z tego pliku.

## 0.2.0 – 2026-11-04

Pierwsze wydanie tej wersji integracji, rozwiniętej z [jarekgrzabel/ha-historia-pojazdu](https://github.com/jarekgrzabel/ha-historia-pojazdu).

### Nowości
- **Formularz konfiguracji**
  - Datę pierwszej rejestracji wybierasz w kalendarzu albo wpisujesz jako `DD.MM.RRRR` (tak jak w dowodzie rejestracyjnym).
  - Błędy wyświetlają się przy konkretnych polach.
  - Przed zapisaniem dane są sprawdzane w usłudze Historia Pojazdu.
- **Zmień konfigurację**: nazwę, numer rejestracyjny i datę możesz zmienić bez usuwania wpisu. VIN jest stały.
- **Sensor licznika** ma `state_class`, więc trafia do statystyk długoterminowych.
- Interfejs jest dostępny również po angielsku.

### Poprawki
- Gdy usługa odrzuci dane pojazdu (4xx), integracja nie ponawia zapytania i pokazuje czytelny komunikat. Błędy 429 i 5xx są nadal ponawiane.
- Nieczytelny odczyt licznika ze starszego badania nie blokuje już poprawnego, nowszego odczytu.
- Logi na poziomie `debug` zawierają typ błędu i kod HTTP, ale nie zawierają VIN ani treści odpowiedzi.
- Zgodność z nowszymi wersjami Home Assistant: `config_entry` przekazywany do koordynatora, dane w `entry.runtime_data`.

### Zmiany, które mogą wymagać uwagi
- Minimalna wersja Home Assistant to **2025.1.0**.
- Z sensorów dat usunięto atrybut `problem`. Ten sam opis pokazuje sensor „Stan pobierania”, więc automatyzacje korzystające z tego atrybutu trzeba przepiąć na ten sensor.
- Wpisy dodane w wersji bazowej działają dalej. Przy ponownym dodaniu tego samego pojazdu duplikat nie zostanie jednak wykryty, ponieważ zmienił się sposób rozpoznawania pojazdu.

### Instalacja
HACS → Niestandardowe repozytoria → `https://github.com/xmemphis-xyz/ha-historia-pojazdu` (typ: Integracja). Szczegóły i przykładowa automatyzacja przypomnień znajdują się w README.

## 0.1.0

Wersja bazowa z [jarekgrzabel/ha-historia-pojazdu](https://github.com/jarekgrzabel/ha-historia-pojazdu): data OC, termin badania technicznego, stan licznika z badania, przycisk odświeżania.
