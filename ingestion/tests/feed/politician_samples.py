# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""What the Bundestag publishes about a member, in the shapes the feed reads:
the Stammdaten, the profile index and a profile, and the vote tables. Shared
by the politician tests."""

from __future__ import annotations

from pathlib import Path

STAMMDATEN = """<?xml version="1.0" encoding="UTF-8"?>
<DOCUMENT>
  <MDB>
    <ID>11005000</ID>
    <NAMEN>
      <NAME><NACHNAME>Alt</NACHNAME><VORNAME>Sanae</VORNAME><AKAD_TITEL/>
        <HISTORIE_VON>26.10.2021</HISTORIE_VON><HISTORIE_BIS>01.01.2022</HISTORIE_BIS></NAME>
      <NAME><NACHNAME>Abdi</NACHNAME><VORNAME>Sanae</VORNAME><AKAD_TITEL>Dr.</AKAD_TITEL>
        <HISTORIE_VON>02.01.2022</HISTORIE_VON><HISTORIE_BIS/></NAME>
    </NAMEN>
    <BIOGRAFISCHE_ANGABEN>
      <GEBURTSDATUM>07.07.1986</GEBURTSDATUM>
      <BERUF>Vertragsmanagerin</BERUF>
      <PARTEI_KURZ>SPD</PARTEI_KURZ>
    </BIOGRAFISCHE_ANGABEN>
    <WAHLPERIODEN>
      <WAHLPERIODE><WP>21</WP><MDBWP_VON>25.03.2025</MDBWP_VON><MDBWP_BIS/>
        <INSTITUTIONEN>
          <INSTITUTION><INSART_LANG>Fraktion/Gruppe</INSART_LANG>
            <INS_LANG>Fraktion der SPD</INS_LANG><MDBINS_BIS/>
            <FKT_LANG>Vorstandsmitglied</FKT_LANG><FKTINS_BIS/></INSTITUTION>
          <INSTITUTION><INSART_LANG>Ministerium</INSART_LANG>
            <INS_LANG>Bundesministerium der Finanzen</INS_LANG><MDBINS_BIS/>
            <FKT_LANG>Parlamentarische Staatssekretärin</FKT_LANG><FKTINS_BIS/></INSTITUTION>
          <INSTITUTION><INSART_LANG>Deutscher Bundestag</INSART_LANG>
            <INS_LANG>Ältestenrat</INS_LANG><MDBINS_BIS/>
            <FKT_LANG>Ordentliches Mitglied</FKT_LANG><FKTINS_BIS/></INSTITUTION>
          <INSTITUTION><INSART_LANG>Ausschuss</INSART_LANG>
            <INS_LANG>Haushaltsausschuss</INS_LANG><MDBINS_BIS/>
            <FKT_LANG>Obfrau</FKT_LANG><FKTINS_BIS/></INSTITUTION>
          <INSTITUTION><INSART_LANG>Fraktion/Gruppe</INSART_LANG>
            <INS_LANG>Fraktion der SPD</INS_LANG><MDBINS_BIS/>
            <FKT_LANG>Justiziarin</FKT_LANG><FKTINS_BIS>01.06.2025</FKTINS_BIS></INSTITUTION>
        </INSTITUTIONEN>
      </WAHLPERIODE>
      <WAHLPERIODE><WP>20</WP><MDBWP_VON>26.10.2021</MDBWP_VON>
        <MDBWP_BIS>25.03.2025</MDBWP_BIS></WAHLPERIODE>
    </WAHLPERIODEN>
  </MDB>
  <MDB>
    <ID>11001478</ID>
    <NAMEN><NAME><NACHNAME>Merkel</NACHNAME><VORNAME>Angela</VORNAME>
      <AKAD_TITEL>Dr.</AKAD_TITEL><HISTORIE_BIS/></NAME></NAMEN>
    <BIOGRAFISCHE_ANGABEN><GEBURTSDATUM>17.07.1954</GEBURTSDATUM>
      <PARTEI_KURZ>CDU</PARTEI_KURZ></BIOGRAFISCHE_ANGABEN>
    <WAHLPERIODEN><WAHLPERIODE><WP>19</WP><MDBWP_VON>24.10.2017</MDBWP_VON>
      <MDBWP_BIS>26.10.2021</MDBWP_BIS></WAHLPERIODE></WAHLPERIODEN>
  </MDB>
</DOCUMENT>"""

INDEX = """<?xml version='1.0' encoding='UTF-8'?>
<mdbUebersicht><mdbs>
  <mdb fraktion="AfD"><mdbID status="Aktiv">9999</mdbID>
    <mdbName status="Aktiv">Abdi, Sanae</mdbName>
    <changedDateTime>01.10.2026 09:00</changedDateTime></mdb>
  <mdb fraktion="SPD"><mdbID status="Aktiv">2314</mdbID>
    <mdbName status="Aktiv">Abdi, Sanae</mdbName>
    <changedDateTime>07.10.2026 14:32</changedDateTime></mdb>
</mdbs></mdbUebersicht>"""

ANGABEN = """<h3>Berufliche Tätigkeit vor der Mitgliedschaft im Deutschen Bundestag</h3>
<ul class="voa_list bt-liste">
 <li>Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ) GmbH, Bonn,
 </li><li>Projekt- und Finanzmanagerin, Rückkehrrecht
</li></ul>
<p><br/></p>
<h3>Entgeltliche Tätigkeiten neben dem Mandat</h3>
<ul class="voa_list bt-liste">
 <li>Publizistische Tätigkeit
  <ul class="bt-liste">
   <li>Aufbau Verlage GmbH &amp; Co. KG, Berlin
   </li><li>2026:\xa010.321,53\xa0EUR, Brutto
  </li></ul>
</li></ul>
<p></p>
<ul class="voa_list bt-liste">
 <li>Vortragstätigkeiten
</li></ul>"""


def profile_xml(bio_id: str = "2314", born: str = "07.07.1986") -> str:
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<mdb><dokumentInfo><dokumentStand>01.04.2025</dokumentStand></dokumentInfo>
<mdbInfo>
  <mdbID status="Aktiv">{bio_id}</mdbID>
  <mdbGeburtsdatum>{born}</mdbGeburtsdatum>
  <mdbBeruf berufsfeld="">Vertrags- und Finanzmanagerin</mdbBeruf>
  <mdbFraktion>SPD</mdbFraktion><mdbPartei>SPD</mdbPartei>
  <mdbLand>Nordrhein-Westfalen</mdbLand>
  <mdbWahlkreis><mdbWahlkreisNummer>092</mdbWahlkreisNummer>
    <mdbWahlkreisName>Köln I</mdbWahlkreisName></mdbWahlkreis>
  <mdbGewaehlt>direkt</mdbGewaehlt>
  <mdbBioURL>https://www.bundestag.de/abgeordnete/biografien/A/abdi_sanae-1043330</mdbBioURL>
  <mdbMitgliedschaften>
    <mdbObleuteGremien title="Obfrau">
      <mdbObleuteGremium id="a19"><gremiumName>Ausschuss für wirtschaftliche Zusammenarbeit und Entwicklung</gremiumName>
        <gremiumURL>https://www.bundestag.de/ausschuesse/entwicklung</gremiumURL></mdbObleuteGremium>
    </mdbObleuteGremien>
    <mdbOrdentlichesMitgliedGremien title="Ordentliches Mitglied">
      <mdbOrdentlichesMitgliedGremium id="a19"><gremiumName>Ausschuss für wirtschaftliche Zusammenarbeit und Entwicklung</gremiumName></mdbOrdentlichesMitgliedGremium>
      <mdbOrdentlichesMitgliedGremium id="pbne"><gremiumName>Parlamentarischer Beirat für nachhaltige Entwicklung und Zukunftsfragen</gremiumName></mdbOrdentlichesMitgliedGremium>
    </mdbOrdentlichesMitgliedGremien>
    <mdbStellvVorsitzSonstigeGremien title="Stellvertretende Vorsitzende">
      <mdbStellvVorsitzSonstigesGremium id="Parlamentariergruppe Maghreb-Staaten"><gremiumName>Parlamentariergruppe Maghreb-Staaten</gremiumName></mdbStellvVorsitzSonstigesGremium>
    </mdbStellvVorsitzSonstigeGremien>
  </mdbMitgliedschaften>
  <mdbVeroeffentlichungspflichtigeAngaben><![CDATA[{ANGABEN}]]></mdbVeroeffentlichungspflichtigeAngaben>
  <mdbVeroeffentlichungspflichtigeAngabenLink>https://www.sanae-abdi.de/</mdbVeroeffentlichungspflichtigeAngabenLink>
  <mdbVeroeffentlichungspflichtigeAngabenLinkPhrase>Individuelle Erläuterungen</mdbVeroeffentlichungspflichtigeAngabenLinkPhrase>
</mdbInfo>
<mdbMedien><mdbFoto>
  <mdbFotoGrossURL>https://www.bundestag.de/resource/image/abdi_sanae.jpg</mdbFotoGrossURL>
  <mdbFotoCopyright>Sanae Abdi/SPD-Fraktion</mdbFotoCopyright>
</mdbFoto></mdbMedien></mdb>"""


VOTES = """<table class="e-table"><thead class="sr-only"><tr>
  <th>Datum</th><th>Titel Abstimmung</th><th>Abstimmungsverhalten</th></tr></thead>
<tbody class="e-table__body">
  <tr class="e-table__row"><td class="e-table__data">15.10.2026</td>
    <td class="e-table__data --break-word"><a class="a-link"
      href="/parlament/plenum/abstimmung/abstimmung/?id=1037">Änderung des
      Brennstoffemissionshandelsgesetzes</a></td>
    <td class="e-table__data"><span class="a-vote --yes">ja</span></td></tr>
  <tr class="e-table__row"><td class="e-table__data">08.10.2026</td>
    <td class="e-table__data"><a class="a-link"
      href="/parlament/plenum/abstimmung/abstimmung/?id=1033">Antrag zur
      Kassenzulassung des nicht-invasiven Pränataltests</a></td>
    <td class="e-table__data"><span class="a-vote --abstain">enthalten</span></td></tr>
  <tr class="e-table__row"><td class="e-table__data">08.10.2026</td>
    <td class="e-table__data"><a class="a-link"
      href="/parlament/plenum/abstimmung/abstimmung/?id=1027">Cum-Cum</a></td>
    <td class="e-table__data"><span class="a-vote --absent">nicht abg.</span></td></tr>
</tbody></table>"""


def roll_call_list(newest: str = "15. Oktober 2026") -> str:
    return f"<div><p>{newest}</p><p>Änderung des Brennstoffemissionshandelsgesetzes</p></div>"


def write_stammdaten(directory: Path) -> Path:
    path = directory / "MDB_STAMMDATEN.XML"
    path.write_text(STAMMDATEN, encoding="utf-8")
    return path
