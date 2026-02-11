import { BorderTrail } from '@/components/ui/border-trail';

function MessageLoadingBorderTrail() {
  return (
    <BorderTrail
      transition={{
        repeat: Number.POSITIVE_INFINITY,
        duration: 2,
        ease: 'linear',
      }}
      style={{
        boxShadow:
          '0px 0px 120px 60px rgb(147 51 234 / 100%), 0 0 200px 120px rgb(59 130 246 / 100%), 0 0 280px 180px rgb(236 72 153 / 100%)',
      }}
    />
  );
}

export default MessageLoadingBorderTrail;
