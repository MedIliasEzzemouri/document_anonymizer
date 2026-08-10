# Pdf_test — synthetic test documents for the anonymizer

16 **fictitious** documents (fake names, emails, IDs, IBANs, etc.) used to test the
document anonymizer. Each file is a different person, in one of three languages
(English / French / Arabic), across many domains.

| # | File | Type | Domain | Language |
|---|------|------|--------|----------|
| 1 | `01_cv_en_sarah_mitchell.tex` | CV | Employment | English |
| 2 | `02_cv_fr_camille_laurent.tex` | CV | Employment | French |
| 3 | `03_cv_ar_hicham_alaoui.tex` | CV | Hospitality | Arabic |
| 4 | `04_hotel_reservation_en_james_carter.tex` | Hotel booking confirmation | Hospitality | English |
| 5 | `05_hotel_contrat_fr_youssef_benali.tex` | Hotel employment contract | Hospitality | French |
| 6 | `06_bank_statement_en_emily_thompson.tex` | Bank statement | Banking | English |
| 7 | `07_bank_ouverture_fr_nadia_haddad.tex` | Bank account opening form | Banking | French |
| 8 | `08_bank_kashf_ar_ahmed_bensalem.tex` | Bank statement | Banking | Arabic |
| 9 | `09_tawkil_ar_legal.tex` | Power of attorney | Legal | Arabic |
| 10 | `10_nda_en_legal.tex` | Non-disclosure agreement | Legal | English |
| 11 | `11_medical_en_daniel_okoro.tex` | Patient discharge summary | Healthcare | English |
| 12 | `12_facture_fr_atelier_lemoine.tex` | Freelance invoice | Billing | French |
| 13 | `13_facture_eau_ar_lamiaa_idrissi.tex` | Water/electricity bill | Utilities | Arabic |
| 14 | `14_offer_letter_en_priya_sharma.tex` | Employment offer letter | HR | English |
| 15 | `15_assurance_auto_fr_karim_benmoussa.tex` | Car insurance certificate | Insurance | French |
| 16 | `16_transcript_en_sofia_rossi.tex` | University transcript | Education | English |

All data is invented for testing — it does not describe real people.

**Arabic note:** Latin text/numbers inside Arabic documents use `\textenglish{...}`
(not `\LR{...}`) to keep phone numbers, IBANs and decimals in correct left-to-right
order. Be aware that the *extracted* text layer of Arabic PDFs may still return digit
groups in logical (reversed-looking) order — relevant when the anonymizer parses them.

## Build

Requires **XeLaTeX** (Arabic needs it) with `polyglossia` + the `Amiri` font.

```bash
# one-time install (macOS):
brew install --cask basictex
sudo /Library/TeX/texbin/tlmgr update --self
sudo /Library/TeX/texbin/tlmgr install polyglossia amiri titlesec enumitem ragged2e collection-langarabic

# then compile all 10:
bash build.sh
```

The PDFs land next to the `.tex` sources.
