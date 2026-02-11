// Type declaration for jsPDF
type JsPDFConstructor = new (options?: {
  orientation?: 'portrait' | 'landscape';
  unit?: string;
  format?: string;
}) => {
  internal: {
    pageSize: {
      getWidth: () => number;
      getHeight: () => number;
    };
  };
  setFontSize: (size: number) => void;
  setFont: (font: string, style: string) => void;
  splitTextToSize: (text: string, maxWidth: number) => string[];
  text: (text: string, x: number, y: number) => void;
  getTextWidth: (text: string) => number;
  line: (x1: number, y1: number, x2: number, y2: number) => void;
  addPage: () => void;
  save: (filename: string) => void;
};

// Content types for the how-to page
export interface HowToSection {
  subtitle?: string;
  list?: string[];
}

export interface HowToAccordionContent {
  intro?: string;
  paragraphs?: string[];
  list?: string[];
  orderedList?: string[];
  sections?: HowToSection[];
  origin?: string;
  outro?: string;
}

export interface HowToAccordionItem {
  id: string;
  title: string;
  content: HowToAccordionContent;
}

export interface HowToIntroText {
  main: string;
  sources: string;
}

export interface HowToPDFExportData {
  introText: HowToIntroText;
  processSteps: string[];
  accordionContent: HowToAccordionItem[];
}

/**
 * Exports the how-to content to a PDF file
 */
export async function exportHowToPDF(data: HowToPDFExportData): Promise<void> {
  // Dynamic import to avoid SSR issues
  const jsPDFModule = (await import('jspdf')) as {
    default: JsPDFConstructor;
  };
  const jsPDF = jsPDFModule.default;

  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 15;
  const maxWidth = pageWidth - 2 * margin;
  let yPosition = margin;

  // Helper function to add text with word wrapping
  const addText = (
    text: string,
    fontSize: number,
    isBold = false,
    isUnderline = false,
  ) => {
    if (yPosition > pageHeight - margin) {
      doc.addPage();
      yPosition = margin;
    }

    doc.setFontSize(fontSize);
    doc.setFont('helvetica', isBold ? 'bold' : 'normal');

    const lines = doc.splitTextToSize(text, maxWidth);
    for (const line of lines) {
      if (yPosition > pageHeight - margin) {
        doc.addPage();
        yPosition = margin;
      }
      doc.text(line, margin, yPosition);
      if (isUnderline) {
        const textWidth = doc.getTextWidth(line);
        doc.line(margin, yPosition + 0.5, margin + textWidth, yPosition + 0.5);
      }
      yPosition += fontSize * 0.5;
    }
    yPosition += 3;
  };

  // Title
  addText('wahl.chat - Anleitung', 18, true, true);
  yPosition += 5;

  // Introduction
  addText(data.introText.main, 11);
  addText(data.introText.sources, 11);
  yPosition += 3;

  // Process steps
  addText('Der Prozess ist einfach:', 12, true);
  data.processSteps.forEach((step, index) => {
    addText(`${index + 1}. ${step}`, 11);
  });
  yPosition += 5;

  // Accordion content
  data.accordionContent.forEach((section) => {
    addText(section.title, 14, true);

    const { content } = section;

    if (content.intro) {
      addText(content.intro, 11);
      if (content.list || content.orderedList || content.sections) {
        yPosition += 2;
      }
    }

    if (content.paragraphs) {
      content.paragraphs.forEach((para) => {
        addText(para, 11);
        yPosition += 2;
      });
    }

    if (content.list) {
      content.list.forEach((item) => {
        addText(`• ${item}`, 11);
      });
      yPosition += 2;
    }

    if (content.orderedList) {
      content.orderedList.forEach((item, index) => {
        addText(`${index + 1}. ${item}`, 11);
        yPosition += 2;
      });
    }

    if (content.sections) {
      content.sections.forEach((subsection) => {
        if (subsection.subtitle) {
          addText(subsection.subtitle, 11, true);
        }
        if (subsection.list) {
          subsection.list.forEach((item) => {
            addText(`• ${item}`, 10);
          });
          yPosition += 2;
        }
      });
    }

    if (content.origin) {
      addText('Wie kam es zu wahl.chat?', 11, true);
      addText(content.origin, 11);
      yPosition += 2;
    }

    if (content.outro) {
      addText(content.outro, 11);
    }

    yPosition += 5;
  });

  // Save the PDF
  doc.save('wahl-chat-anleitung.pdf');
}
