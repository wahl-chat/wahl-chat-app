import DonationDialog from '@/components/donation-dialog';
import { Button } from '@/components/ui/button';
import { HeartHandshakeIcon } from 'lucide-react';
import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Über uns',
  description:
    'Das Team hinter wahl.chat – wer wir sind und warum wir Politik interaktiv zugänglich machen.',
  robots: 'noindex',
};

function AboutUs() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center justify-center space-y-6 pt-4">
      <div className="relative aspect-[4/3] w-full">
        <Image
          src="/images/team.webp"
          alt="About Us"
          fill
          sizes="(max-width: 768px) 100vw, 75vw"
          className="object-cover"
        />
      </div>
      <section className="space-y-4">
        <p>
          <span className="font-bold [&_a]:underline">
            Hinter <Link href="http://wahl.chat/">wahl.chat</Link> stehen:{' '}
            <a href="https://www.linkedin.com/in/sebmai/" target="_blank">
              Sebastian
            </a>
            ,{' '}
            <a href="https://www.linkedin.com/in/antonwy/" target="_blank">
              Anton
            </a>
            ,{' '}
            <a
              href="https://www.linkedin.com/in/michel-schimpf-55069b198/"
              target="_blank"
            >
              Michel
            </a>
            ,{' '}
            <a href="https://www.linkedin.com/in/robin-frasch/" target="_blank">
              Robin
            </a>
            ,{' '}
            <a href="https://www.linkedin.com/in/roman-mayr/" target="_blank">
              Roman
            </a>{' '}
          </span>
          (im Bild von links nach rechts)
        </p>

        <p>
          Das Team von wahl.chat stammt aus München und hat sich ursprünglich in
          Cambridge, UK zur gemeinsamen Forschung an KI zusammengefunden.
          Mittlerweile sind wir über drei Länder verstreut aber haben weiterhin
          ein gemeinsames Ziel: Mit wahl.chat möchten wir einen Beitrag zur
          Demokratie leisten, indem wir Politik leichter zugänglich machen.
          Basierend auf den Grundsatzprogrammen und Positionspapieren der
          Parteien ermöglichen wir eine einfache, quellengestützte
          Informationsmöglichkeit mit der wir politische Bildung neu denken.
        </p>
        <p className="[&_a]:underline">
          Zudem bedanken wir uns für ihre Unterstützung bei:{' '}
          <a target="_blank" href="https://www.linkedin.com/in/simonkaran/">
            Simon
          </a>
          ,{' '}
          <a
            target="_blank"
            href="https://www.linkedin.com/in/nathan-orester-898014247/"
          >
            Nathan
          </a>
          ,{' '}
          <a
            target="_blank"
            href="https://www.linkedin.com/in/anton-kluge-0b0aa6220/"
          >
            Anton
          </a>
          ,{' '}
          <a
            target="_blank"
            href="https://www.linkedin.com/in/paul-barbu-8391b7216/"
          >
            Paul
          </a>
          ,{' '}
          <a target="_blank" href="https://www.linkedin.com/in/etiennekoehler/">
            Etienne
          </a>
          ,{' '}
          <a target="_blank" href="https://www.linkedin.com/in/nikhil-j-roy/">
            Nikhil
          </a>
          , Mai
        </p>
        <p className="[&_a]:underline">
          Wenn du uns helfen möchtest, kannst du gerne Teil des{' '}
          <Link href="http://wahl.chat/">wahl.chat</Link> Teams werden. Melde
          dich einfach unter: <a href="mailto:info@wahl.chat">info@wahl.chat</a>
        </p>
        <p className="[&_a]:underline">
          Es besteht auch die Möglichkeit, eine Bachelor- oder Masterarbeit bei
          uns zu schreiben. Melde dich hierfür am besten mit einem
          Themenvorschlag direkt bei{' '}
          <a href="mailto:robin@wahl.chat">robin@wahl.chat</a>
        </p>

        <div className="flex items-center justify-between gap-4 rounded-md border border-border p-4">
          <div className="flex flex-col">
            <h2 className="font-bold">Unterstütze uns</h2>
            <p className="text-sm text-muted-foreground">
              Hilf uns, laufende Kosten für die KI zu decken!
            </p>
          </div>

          <DonationDialog>
            <Button>
              <HeartHandshakeIcon />
              Spenden
            </Button>
          </DonationDialog>
        </div>
      </section>
    </div>
  );
}

export default AboutUs;
