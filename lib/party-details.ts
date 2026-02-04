export type PartyDetails = {
  name: string;
  candidate?: string;
  long_name: string;
  website_url: string;
  description?: string;
  party_id: string;
  background_color?: string;
  election_manifesto_url?: string;
  manifesto_url?: string;
  election_result_forecast_percent?: number;
  is_already_in_parliament?: boolean;
  is_small_party?: boolean;
  logo_src?: string;
};
