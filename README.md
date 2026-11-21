# The Passport Page of a Country That Isn't There

Entry for the make.fun competition
`the-passport-page-of-a-countr-2-20261121-0318`.

`main.py` (Python 3.13, stdlib only, no network, deterministic) draws one
invented passport spread — the Republic of Meridia, an island nation that
does not exist — and writes it to `/output/entry.png` (1024×640, PNG).

Left page: data page with a portrait, the holder's details, and a
machine-readable zone with ICAO 9303 check digits. Right page: a Dravnian
visa, entry/exit stamps from three neighbouring countries, and an
endorsement stamp — re-entry to Meridia by ferry only, because the island
has no airport. Every date agrees: the passport was issued 02 JUN 2023 and
expires 02 JUN 2033, every stamp falls inside that span, and the Dravnian
stay (12–28 SEP 2024) fits its 30-day visa.

## Run

```sh
python3 main.py            # writes /output/entry.png
OUTPUT_DIR=./out python3 main.py   # local test into ./out/entry.png
```

Two runs produce byte-identical output.

## License

MIT — see `LICENSE`.
