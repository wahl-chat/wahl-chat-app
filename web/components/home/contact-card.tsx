import HomeSocialMediaIcon from '@/components/icons/home-social-media-icon';

/**
 * Cards render an h2 by default, which is right on the election home page
 * where each card is a top-level block. Under a section heading on the
 * landing page they must be h3 so the outline does not flatten.
 */
type CardTitleProps = {
  titleAs?: 'h2' | 'h3';
};

function ContactCard({ titleAs: Title = 'h2' }: CardTitleProps) {
  return (
    <div className="flex flex-col rounded-md border border-border">
      <div className="flex grow flex-col justify-between p-4">
        <div>
          <Title className="font-bold">Bleibe up to date</Title>
          <p className="text-sm text-muted-foreground">
            Finde uns auf Social Media oder kontaktiere uns per E-Mail.
          </p>
        </div>
        <div className="mt-4 flex flex-row items-center gap-3">
          <HomeSocialMediaIcon type="instagram" />
          <HomeSocialMediaIcon type="linkedin" />
          <HomeSocialMediaIcon type="email" />
        </div>
      </div>
    </div>
  );
}

export default ContactCard;
