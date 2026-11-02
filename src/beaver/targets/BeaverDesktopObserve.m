// Read-only macOS cursor/frontmost-PID observation for bounded test evidence.
// No event posting, cursor positioning, activation, AX or input capture.
#import <Cocoa/Cocoa.h>
#import <ApplicationServices/ApplicationServices.h>
#include <unistd.h>
int main(int argc,const char **argv) {
    @autoreleasepool {
        if(argc!=3)return 2;
        char *end1=NULL,*end2=NULL;long duration=strtol(argv[1],&end1,10),interval=strtol(argv[2],&end2,10);
        if(!end1||*end1||!end2||*end2||duration<1||duration>60000||interval<20||interval>1000)return 2;
        NSMutableArray *samples=[NSMutableArray array];CFAbsoluteTime start=CFAbsoluteTimeGetCurrent();
        do {
            @autoreleasepool {
                CGEventRef event=CGEventCreate(NULL);CGPoint p=event?CGEventGetLocation(event):CGPointZero;
                pid_t front=NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier;
                [samples addObject:@{@"elapsedMs":@((long)((CFAbsoluteTimeGetCurrent()-start)*1000)),@"frontmostPid":@(front),@"cursorReadable":@(event!=NULL),@"x":@(p.x),@"y":@(p.y)}];
                if(event)CFRelease(event);
            }
            if((CFAbsoluteTimeGetCurrent()-start)*1000>=duration)break;
            usleep((useconds_t)interval*1000);
        }while(YES);
        NSDictionary *result=@{@"contract":@"beaver-readonly-desktop-observation/1",@"observerPid":@(getpid()),@"effects":@"none",@"samples":samples};
        NSData *data=[NSJSONSerialization dataWithJSONObject:result options:0 error:NULL];
        if(!data)return 3;fwrite(data.bytes,1,data.length,stdout);fputc('\n',stdout);
    }
    return 0;
}
