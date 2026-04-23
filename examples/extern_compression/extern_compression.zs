package extern_compression;

enum uint8 CompressionType
{
    NO_COMPRESSION = 0,
    ZLIB = 1,
    ZSTD = 2,
    LZ4 = 3,
    BROTLI = 4
};

struct Payload
{
    string name;
    uint32 value;
    string tags[];
};

struct CompressedBlob
{
    CompressionType compressionType;
    extern data;
};
