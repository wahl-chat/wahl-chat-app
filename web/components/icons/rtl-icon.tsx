import { cn } from '@/lib/utils';

type Props = {
  className?: string;
};

function RtlIcon({ className }: Props) {
  return (
    <svg
      className={cn('w-12', className)}
      width="174"
      height="31"
      viewBox="0 0 174 31"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g clipPath="url(#clip0_68_22)">
        <path d="M174 0H119.62V31H174V0Z" fill="#9629BC" />
        <path
          d="M136.521 7.125H140.296V20.5735H157.1V23.8753H136.521V7.125Z"
          fill="white"
        />
        <path d="M114.192 0H59.8121V31H114.192V0Z" fill="#0CAAED" />
        <path
          d="M85.1105 10.4268H75.5536V7.125H98.4464V10.4268H88.8895V23.8753H85.1105V10.4268Z"
          fill="white"
        />
        <path d="M54.3796 0H0V31H54.3796V0Z" fill="#0C39ED" />
        <path
          d="M15.446 7.125H29.9368C34.3488 7.125 36.8042 9.13566 36.8042 12.5075C36.8042 15.401 34.9627 17.3417 31.8244 17.7967L38.9297 23.8753H33.4779L26.7985 18.0106H19.2251V23.8715H15.4499V7.125H15.446ZM29.4419 14.876C31.7783 14.876 32.9101 14.1098 32.9101 12.5542C32.9101 10.9985 31.7783 10.2557 29.4419 10.2557H19.2251V14.8721H29.4419V14.876Z"
          fill="white"
        />
        <g opacity="0.3" />
      </g>
      <defs>
        <clipPath id="clip0_68_22">
          <rect width="174" height="31" fill="white" />
        </clipPath>
      </defs>
    </svg>
  );
}

export default RtlIcon;
