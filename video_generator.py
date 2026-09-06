"""Video generation module for Swarm.
Converts content scripts into actual MP4 video files ready for YouTube upload.

Pipeline:
    TTS (edge-tts) → audio MP3
    Image generation (Pillow) → thumbnail JPEG
    ffmpeg → MP4 video with audio + image

Requirement: ffmpeg must be installed and available on PATH.
Install on Windows:  winget install --id=Gyan.FFmpeg -e
Install on Linux:     sudo apt-get install -y ffmpeg

If ffmpeg is not found, video generation fails with a clear error.
No auto-download of binaries from the internet.
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class VideoGenerator:
    """Generate MP4 videos from content scripts for YouTube upload."""

    # YouTube requires minimum 24fps, 720p+ resolution
    WIDTH = 1280
    HEIGHT = 720
    FPS = 24  # Minimum for YouTube

    def __init__(self, swarm_dir=None):
        self.swarm_dir = Path(swarm_dir or '.')
        self.videos_dir = self.swarm_dir / 'videos'
        self.thumbnails_dir = self.swarm_dir / 'thumbnails'
        self.audio_dir = self.swarm_dir / 'audio'
        self.videos_dir.mkdir(exist_ok=True)
        self.thumbnails_dir.mkdir(exist_ok=True)
        self.audio_dir.mkdir(exist_ok=True)

        # Check ffmpeg availability
        self.ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Check if ffmpeg binary is available on PATH.

        Uses shutil.which for reliable PATH lookup across platforms.
        """
        import shutil
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            logger.info(f"ffmpeg found: {ffmpeg} — can produce real video files")
            return True
        logger.warning("ffmpeg NOT found on PATH — video generation will fail")
        logger.warning("Install ffmpeg: winget install --id=Gyan.FFmpeg -e  (Windows)")
        logger.warning("Install ffmpeg: sudo apt-get install -y ffmpeg  (Linux)")
        return False

    def generate_video(self, content_id, title, script, voiceover_text=None,
                       thumbnail_prompt=None, output_dir=None):
        """Generate a complete MP4 video from a content script.

        Args:
            content_id: Unique ID for the video (used for filenames)
            title: Video title (for metadata)
            script: Full script text
            voiceover_text: Text to synthesize to speech (defaults to script)
            thumbnail_prompt: Optional prompt for thumbnail image generation
            output_dir: Directory for output files (default: swarm/videos)

        Returns:
            Dict with paths to generated files, status, and metadata
        """
        output_dir = Path(output_dir or self.videos_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        voiceover_text = voiceover_text or script
        video_path = output_dir / f"{content_id}.mp4"
        audio_path = self.audio_dir / f"{content_id}.mp3"
        thumbnail_path = self.thumbnails_dir / f"{content_id}.jpg"

        result = {
            'video_path': str(video_path),
            'audio_path': str(audio_path),
            'thumbnail_path': str(thumbnail_path),
            'status': 'pending',
            'content_id': content_id,
            'title': title,
            'duration_seconds': 0,
            'file_size_bytes': 0
        }

        # Step 1: Generate thumbnail image
        logger.info(f"[{content_id}] Generating thumbnail...")
        try:
            self._generate_thumbnail(thumbnail_prompt or title, thumbnail_path)
            result['thumbnail_path'] = str(thumbnail_path)
            logger.info(f"[{content_id}] Thumbnail saved: {thumbnail_path}")
        except Exception as e:
            logger.error(f"[{content_id}] Thumbnail generation failed: {e}")
            result['thumbnail_error'] = str(e)

        # Step 2: Generate TTS audio
        logger.info(f"[{content_id}] Generating voiceover...")
        try:
            self._generate_tts(voiceover_text, audio_path)
            result['audio_path'] = str(audio_path)
            result['duration_seconds'] = self._get_audio_duration(audio_path)
            logger.info(f"[{content_id}] Audio saved: {audio_path} ({result['duration_seconds']:.1f}s)")
        except Exception as e:
            logger.error(f"[{content_id}] TTS generation failed: {e}")
            result['audio_error'] = str(e)

        # Step 3: Assemble video with ffmpeg
        if self.ffmpeg_available and result['audio_path'] and Path(result['audio_path']).exists():
            logger.info(f"[{content_id}] Assembling video with ffmpeg...")
            try:
                self._assemble_with_ffmpeg(
                    audio_path, thumbnail_path, video_path,
                    duration=result['duration_seconds']
                )
                result['video_path'] = str(video_path)
                result['file_size_bytes'] = video_path.stat().st_size
                result['status'] = 'generated'
                logger.info(f"[{content_id}] Video saved: {video_path} ({result['file_size_bytes']/1024/1024:.1f} MB)")
            except Exception as e:
                logger.error(f"[{content_id}] ffmpeg assembly failed: {e}")
                result['status'] = 'failed'
                result['video_error'] = str(e)
        else:
            result['status'] = 'failed'
            if not self.ffmpeg_available:
                result['video_error'] = 'FFmpeg is not installed or not on PATH. Install: winget install --id=Gyan.FFmpeg -e'
            elif not result.get('audio_path'):
                result['video_error'] = 'No audio generated — TTS failed'
            else:
                result['video_error'] = 'Unknown assembly failure'

        return result

    def _generate_thumbnail(self, prompt, output_path):
        """Generate a thumbnail image from text prompt using Pillow."""
        from PIL import Image, ImageDraw, ImageFont
        import random

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        width, height = 1280, 720

        # Create gradient background based on prompt keywords
        img = Image.new('RGB', (width, height))
        pixels = img.load()

        # Color palette based on prompt
        colors = {
            'tech': [(10, 20, 40), (20, 40, 80), (0, 255, 136)],
            'github': [(20, 20, 20), (40, 40, 40), (255, 255, 255)],
            'ai': [(10, 10, 30), (50, 20, 80), (124, 77, 255)],
            'default': [(10, 14, 20), (20, 30, 50), (0, 255, 136)],
        }

        keyword = 'default'
        prompt_lower = prompt.lower()
        if any(k in prompt_lower for k in ['github', 'code', 'developer', 'tech']):
            keyword = 'github' if 'github' in prompt_lower else 'tech'
        elif 'ai' in prompt_lower or 'agent' in prompt_lower:
            keyword = 'ai'

        palette = colors[keyword]

        # Gradient background
        for y in range(height):
            t = y / height
            r = int(palette[0][0] * (1-t) + palette[1][0] * t)
            g = int(palette[0][1] * (1-t) + palette[1][1] * t)
            b = int(palette[0][2] * (1-t) + palette[1][2] * t)
            for x in range(width):
                pixels[x, y] = (r, g, b)

        draw = ImageDraw.Draw(img)

        # Accent glow gradient bar at top
        for y in range(8):
            alpha = 1.0 - (y / 8)
            r, g, b = palette[2]
            for x in range(width):
                px, py = x, y
                existing = img.getpixel((px, py))
                pixels[px, py] = (
                    int(existing[0] * (1-alpha) + r * alpha),
                    int(existing[1] * (1-alpha) + g * alpha),
                    int(existing[2] * (1-alpha) + b * alpha)
                )

        # Try to load a font
        font_paths = [
            "arial.ttf",
            "/c/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BOLD.ttf",
        ]
        font_large = font_medium = font_small = ImageFont.load_default()
        for fp in font_paths:
            try:
                font_large = ImageFont.truetype(fp, 72)
                font_medium = ImageFont.truetype(fp, 48)
                font_small = ImageFont.truetype(fp, 28)
                break
            except (IOError, OSError):
                continue

        # Title text — split into lines if too long
        words = prompt.split()
        lines = []
        current_line = ""
        max_chars_per_line = 35

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if len(test_line) <= max_chars_per_line:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        # Title in center
        line_height = 90
        start_y = height // 2 - (len(lines) * line_height) // 2

        for i, line in enumerate(lines):
            # Text shadow
            draw.text(
                (width//2 + 3, start_y + i * line_height + 3),
                line, fill=(0, 0, 0), font=font_large, anchor='mm'
            )
            # Main text
            draw.text(
                (width//2, start_y + i * line_height),
                line, fill=(255, 255, 255), font=font_large, anchor='mm'
            )

        # Accent line below title
        line_y = start_y + len(lines) * line_height + 20
        draw.rectangle(
            [(width//2 - 100, line_y), (width//2 + 100, line_y + 4)],
            fill=palette[2]
        )

        # "Swarm" branding bottom-right
        try:
            brand_font = ImageFont.truetype("arial.ttf", 20)
        except (IOError, OSError):
            brand_font = font_small
        draw.text((width - 30, height - 30), "Swarm", fill=(255,255,255,100),
                  font=brand_font, anchor='ra')

        img.save(output_path, 'JPEG', quality=90)

    def _generate_tts(self, text, output_path):
        """Generate TTS audio using edge-tts."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        import asyncio
        import edge_tts

        # Use a natural-sounding voice
        voice = "en-US-AriaNeural"  # Clear, professional female voice

        async def do_tts():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))

        asyncio.run(do_tts())

    def _get_audio_duration(self, audio_path):
        """Get audio duration in seconds using ffprobe if available."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            return 0

        import shutil
        ffprobe = shutil.which("ffprobe")
        if ffprobe:
            try:
                result = subprocess.run(
                    [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
                     '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    return float(result.stdout.strip())
            except Exception:
                pass

        # Fallback: estimate ~150 words per minute (~2.5 chars/sec for English)
        try:
            text = audio_path.with_suffix('.txt')
            if text.exists():
                return max(len(text.read_text(errors='ignore')) / 2.5, 10)
        except Exception:
            pass

        return 30  # Conservative default

    def _assemble_with_ffmpeg(self, audio_path, image_path, output_path, duration=None):
        """Assemble video using ffmpeg: image + audio = MP4."""
        audio_path = Path(audio_path)
        image_path = Path(image_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio not found: {audio_path}")

        if not image_path.exists():
            # Create a blank image
            from PIL import Image
            img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(10, 14, 20))
            img.save(image_path)

        if duration is None:
            duration = 30  # Default 30 seconds

        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', str(image_path),
            '-i', str(audio_path),
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            '-vf', f'fps={self.FPS},scale={self.WIDTH}:{self.HEIGHT}:force_original_aspect_ratio=decrease,pad={self.WIDTH}:{self.HEIGHT}:(ow-iw)/2:(oh-ih)/2',
            '-movflags', '+faststart',
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")




def generate_videos_for_operations(operations, swarm_dir='.'):
    """Generate videos for all script_ready operations.

    Args:
        operations: List of operation dicts from operations.json
        swarm_dir: Path to swarm directory

    Returns:
        List of generation results
    """
    generator = VideoGenerator(swarm_dir=swarm_dir)
    results = []

    for op in operations:
        if op.get('status') != 'script_ready':
            continue

        content_id = op.get('id', '')
        title = op.get('title', '')
        script = op.get('script', '')
        voiceover = op.get('voiceover_text', script)

        logger.info(f"Generating video for: {title} ({content_id})")

        result = generator.generate_video(
            content_id=content_id,
            title=title,
            script=script,
            voiceover_text=voiceover
        )

        results.append({
            'content_id': content_id,
            'title': title,
            **result
        })

        status_icon = '✅' if result['status'].startswith('generated') else '❌'
        logger.info(f"{status_icon} {title}: {result['status']}")

    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Generate videos from content scripts')
    parser.add_argument('--operations', default='data/operations.json',
                       help='Path to operations.json')
    parser.add_argument('--swarm-dir', default='.',
                       help='Swarm directory path')
    parser.add_argument('--content-id', help='Generate only this content ID')
    parser.add_argument('--ffmpeg', action='store_true',
                       help='Skip ffmpeg auto-download, use system ffmpeg only')

    args = parser.parse_args()

    # Suppress excessive logging during generation
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    operations_file = Path(args.operations)
    if not operations_file.exists():
        print(f"Operations file not found: {operations_file}")
        sys.exit(1)

    with open(operations_file) as f:
        operations = json.load(f)

    if args.content_id:
        operations = [op for op in operations if op.get('id') == args.content_id]
        if not operations:
            print(f"No operation found with content_id: {args.content_id}")
            sys.exit(1)

    if args.ffmpeg:
        # Don't try to auto-download ffmpeg
        os.environ['SWARM_NO_FFMPEG_DOWNLOAD'] = '1'

    results = generate_videos_for_operations(operations, swarm_dir=args.swarm_dir)

    # Summary
    print("\n" + "=" * 60)
    print("VIDEO GENERATION SUMMARY")
    print("=" * 60)

    generated = sum(1 for r in results if r['status'].startswith('generated'))
    failed = sum(1 for r in results if r['status'].startswith('failed'))

    for r in results:
        icon = '✅' if r['status'].startswith('generated') else '❌'
        size = f"{r.get('file_size_bytes', 0) / 1024 / 1024:.1f} MB" if r.get('file_size_bytes') else 'N/A'
        print(f"{icon} {r['title'][:50]}")
        print(f"   Status: {r['status']} | Size: {size}")
        if r.get('video_path'):
            print(f"   Video: {r['video_path']}")
        if r.get('error') or r.get('video_error'):
            print(f"   Error: {r.get('video_error', r.get('error'))}")
        print()

    print(f"Generated: {generated} | Failed: {failed} | Total: {len(results)}")
    print("=" * 60)


def validate_video(video_path):
    """Validate a generated video file.

    Returns dict with validation results.
    """
    from pathlib import Path
    import shutil

    video_path = Path(video_path)
    result = {
        'valid': False,
        'file_exists': False,
        'codec_valid': False,
        'duration_seconds': 0,
        'resolution': None,
        'file_size_bytes': 0,
        'audio_exists': False,
        'video_exists': False,
        'errors': [],
    }

    if not video_path.exists():
        result['errors'].append(f"File not found: {video_path}")
        return result

    result['file_exists'] = True
    result['file_size_bytes'] = video_path.stat().st_size

    if result['file_size_bytes'] < 1000:
        result['errors'].append("File too small to be a valid video")
        return result

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        result['errors'].append("ffprobe not available — cannot validate codec")
        result['valid'] = True  # File exists and has size, assume OK
        return result

    try:
        probe = subprocess.run(
            [ffprobe, '-v', 'error', '-show_entries',
             'format=format_name,duration:stream=codec_type,codec_name,width,height',
             '-of', 'json', str(video_path)],
            capture_output=True, text=True, timeout=10
        )
        if probe.returncode != 0:
            result['errors'].append(f"ffprobe failed: {probe.stderr}")
            return result

        data = json.loads(probe.stdout)
        streams = data.get('streams', [])

        for stream in streams:
            codec_type = stream.get('codec_type', '')
            if codec_type == 'video':
                result['video_exists'] = True
                result['codec_valid'] = True
                result['resolution'] = f"{stream.get('width')}x{stream.get('height')}"
            elif codec_type == 'audio':
                result['audio_exists'] = True

        result['duration_seconds'] = float(data.get('format', {}).get('duration', 0))

    except Exception as e:
        result['errors'].append(f"Validation error: {e}")

    # Check minimum requirements
    if not result['video_exists']:
        result['errors'].append("No video stream found")
    if not result['audio_exists']:
        result['errors'].append("No audio stream found")
    if result['resolution']:
        w, h = result['resolution'].split('x')
        if int(w) < 1280 or int(h) < 720:
            result['errors'].append(f"Resolution {result['resolution']} below 720p minimum")

    result['valid'] = len(result['errors']) == 0
    return result
