package perf;

struct Point
{
    int32 x;
    int32 y;
};

struct Record
{
    uint32 id;
    string label;
    Point points[];
};

struct Dataset
{
    string name;
    Record records[];
};
