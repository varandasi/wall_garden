module Ai
  # Down-sizes JPEGs so vision calls stay cheap and fast.
  # Anthropic recommends ≤1568 px on the long edge for best price/perf.
  class ImagePreparer
    MAX_LONG_EDGE = 1024

    def self.prepare(path)
      return path unless File.exist?(path)

      img = MiniMagick::Image.open(path)
      long = [img.width, img.height].max
      return path if long <= MAX_LONG_EDGE

      out = Rails.root.join('tmp', 'ai_images', File.basename(path))
      FileUtils.mkdir_p(File.dirname(out))
      img.resize "#{MAX_LONG_EDGE}x#{MAX_LONG_EDGE}>"
      img.format 'jpg'
      img.write(out.to_s)
      out.to_s
    rescue MiniMagick::Error => e
      Rails.logger.warn("ImagePreparer failed for #{path}: #{e.message}")
      path  # fall back to original
    end
  end
end
