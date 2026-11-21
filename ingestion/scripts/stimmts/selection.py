"""The votes chosen for Stimmt's?, by Abgeordnetenwatch poll id, with the reason.

The reasons appear in docs/stimmts/puzzle-selection.md, so the choice can be
defended as neutral. Changing a pick here only changes what is drafted; the
game plays what is committed in web/lib/stimmts/content/.
"""

PICKS: dict[int, str] = {
    6733: "Climate and fuel prices; Die Linke abstains",
    6730: "Bundeswehr missions need parliament; the Greens abstain",
    6724: "Tax on crypto gains; young audience",
    6682: "Headline topic; AfD votes with the coalition",
    6683: "Profits from high energy prices (keep apart from the Tankrabatt)",
    6662: "Police powers; AfD abstains",
    6605: "The Heizungsgesetz debate",
    6601: "Health-insurance contributions affect everyone",
    6606: "Lighter topic; only Die Linke against",
    6600: "Classic debate; only Linke and Grüne in favour",
    6598: "Only the Greens vote yes",
    6552: "Climate targets; the Greens abstain",
    6551: 'Student aid ("Ja" means rejecting a motion)',
    6498: "Electricity tax for all; unusual opposition alliance",
    6422: "Bürgergeld becomes Grundsicherung",
    6419: "EU asylum reform",
    6391: "AfD alone against all others",
    6373: "Consumer protection online",
    6356: "Pensions; Die Linke abstains",
    6359: "Military service, relevant to young people",
    6353: "Humanitarian admissions from Afghanistan",
    6351: "The federal budget",
    6323: "Two parties abstain",
    6329: "Electricity grid costs; three parties abstain",
    6311: "Rents, relevant to young people",
    6286: 'Combustion-engine ban ("Ja" means rejecting a motion)',
    6280: "Citizenship law; AfD votes with the coalition",
    6249: 'Nuclear plants ("Ja" means rejecting a motion)',
    6170: 'Corona inquiry ("Ja" means rejecting a motion)',
    6155: "Family reunification; AfD votes with the coalition",
}

SPARES: dict[int, str] = {
    6357: "Safe countries of origin",
    6372: 'Tax privileges for the largest inheritances ("Ja" means rejecting)',
    6575: "Last extension of the Lebanon mission",
    6664: "Climate adaptation in the Grundgesetz",
    6566: "Paternity recognition; AfD abstains",
}
