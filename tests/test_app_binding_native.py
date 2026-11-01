"""Compile the native bridge and exercise only rejection paths, never UI input."""
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'src/beaver/targets/BeaverAppBinding.m'

@unittest.skipUnless(platform.system()=='Darwin','macOS AX bridge')
class AppBindingNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=SOURCE.parents[3]/'.private/app-binding-native/tests'
        root.mkdir(parents=True,exist_ok=True)
        cls.directory=tempfile.TemporaryDirectory(dir=root);cls.root=Path(cls.directory.name)
        cls.binary=cls.root/'bridge';cls.denied=cls.root/'denied';cls.routing=cls.root/'routing'
        cls.flags=['xcrun','clang','-fobjc-arc','-Wall','-Wextra','-Werror','-framework','Foundation','-framework','AppKit','-framework','ApplicationServices']
        subprocess.run(cls.flags+[str(SOURCE),'-o',str(cls.binary)],check=True,capture_output=True)
        shim=cls.root/'denied.m'
        shim.write_text('#import <Foundation/Foundation.h>\n#import <AppKit/AppKit.h>\n#import <ApplicationServices/ApplicationServices.h>\nstatic Boolean TestAXIsProcessTrusted(void){return false;}\n#define AXIsProcessTrusted TestAXIsProcessTrusted\n#include "'+str(SOURCE)+'"\n')
        subprocess.run(cls.flags+[str(shim),'-o',str(cls.denied)],check=True,capture_output=True)
        routing=cls.root/'routing.m'
        routing.write_text('#define main BeaverBindingMain\n#include "'+str(SOURCE)+'"\n#undef main\n'+r'''int main(void){@autoreleasepool {
            BOOL ok=YES;NSUInteger checked=0;
            NSArray *geometries=@[@{@"x":@140,@"y":@470,@"width":@480,@"height":@332},@{@"x":@(-1920),@"y":@0,@"width":@1024,@"height":@768},@{@"x":@0,@"y":@(-200),@"width":@640,@"height":@1000}];
            NSArray *types=@[@(NSEventTypeLeftMouseDown),@(NSEventTypeLeftMouseUp),@(NSEventTypeLeftMouseDragged),@(NSEventTypeRightMouseDown),@(NSEventTypeRightMouseUp),@(NSEventTypeRightMouseDragged)];
            for(NSDictionary *bounds in geometries) {
                NSArray *points=@[@{@"x":@0,@"y":@0},@{@"x":@190.25,@"y":@183.5},@{@"x":@([bounds[@"width"] doubleValue]-.5),@"y":@([bounds[@"height"] doubleValue]-.5)}];
                for(NSDictionary *point in points)for(NSNumber *type in types){
                    response=[NSMutableDictionary dictionaryWithDictionary:@{@"selectedWindow":@{@"windowId":@12345,@"bounds":bounds}}];
                    CGEventRef event=WindowMouseEvent([type unsignedIntegerValue],point);RouteMouse(event,12345);
                    NSEvent *roundtrip=[NSEvent eventWithCGEvent:event];CGPoint at=CGEventGetLocation(event);
                    ok=ok&&roundtrip.windowNumber==12345&&fabs(at.x-[point[@"x"] doubleValue])<.001&&fabs(at.y-[point[@"y"] doubleValue])<.001&&[response[@"constructionAttempts"] unsignedIntegerValue]<=2&&CGEventGetIntegerValueField(event,kCGMouseEventWindowUnderMousePointer)==12345&&CGEventGetIntegerValueField(event,kCGMouseEventWindowUnderMousePointerThatCanHandleThisEvent)==12345&&CGEventGetIntegerValueField(event,kCGMouseEventClickState)==1&&CGEventGetIntegerValueField(event,kCGMouseEventNumber)==1;
                    CFRelease(event);checked++;
                }
            }
            BOOL outside=NO;@try {WindowMouseEvent(NSEventTypeLeftMouseDown,@{@"x":@(-1),@"y":@0});} @catch(NSException *e){outside=[response[@"errorCode"] isEqual:@"POINT_OUTSIDE_WINDOW"];}
            CGRect display=CGDisplayBounds(CGMainDisplayID());NSDictionary *receipt=@{@"cases":@(checked),@"eventsPosted":@(posted),@"outsideRefused":@(outside),@"displayBounds":@[@(display.origin.x),@(display.origin.y),@(display.size.width),@(display.size.height)],@"passed":@(ok&&outside&&posted==0)};
            NSData *out=[NSJSONSerialization dataWithJSONObject:receipt options:0 error:nil];fwrite(out.bytes,1,out.length,stdout);
            return ok&&outside&&posted==0?0:1;
        }}''')
        subprocess.run(cls.flags+[str(routing),'-o',str(cls.routing)],check=True,capture_output=True)


    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def request(self,**changes):
        return dict(operation='windows',pid=2147483647,startTime=[1,0],executableDevice=1,executableInode=1,bundleIdentifier='invalid.no.running.app',**changes)

    def blocked(self,value,code=None,binary=None):
        raw=value if isinstance(value,bytes) else json.dumps(value).encode()
        result=subprocess.run([str(binary or self.binary)],input=raw,capture_output=True,timeout=12)
        self.assertEqual(result.returncode,3,result.stdout)
        output=json.loads(result.stdout);self.assertEqual(output['status'],'blocked');self.assertEqual(output['eventsPosted'],0);self.assertEqual(output['inputDelivery'],'not-posted');self.assertEqual(result.stderr,b'')
        if code:self.assertEqual(output['errorCode'],code)
        return output

    def test_permission_denial_never_prompts_or_posts(self):
        self.blocked(self.request(),'AX_PERMISSION_REQUIRED',self.denied)
        close=self.request();close.update(operation='close',windowId=1)
        result=self.blocked(close,'AX_PERMISSION_REQUIRED',self.denied)
        self.assertEqual(result['axActionsAttempted'],0)

    def test_invalid_json_size_unknown_fields_and_types(self):
        self.blocked(b'{broken','INVALID_JSON')
        self.blocked(b' '*65537,'REQUEST_TOO_LARGE')
        for changes in [{'pid':True},{'pid':1.5},{'startTime':[1,1000000]},{'executableInode':False},{'unexpected':'no'},{'operation':'launch'}]:
            request=self.request();request.update(changes)
            with self.subTest(changes=changes):self.blocked(request,'INVALID_OPERATION' if changes.get('operation')=='launch' else 'INVALID_REQUEST')

    def test_input_requests_reject_before_permissions_or_events(self):
        bad=[dict(operation='click',windowId=1,x=0,y=0,button='middle'),dict(operation='click',x=0,y=0),dict(operation='key',windowId=1,key='arbitrary-key'),dict(operation='key',windowId=1,key='return',flags=1),dict(operation='text',windowId=1,text='x'*257),dict(operation='drag',windowId=1,points=[dict(x=0,y=0)]*65)]
        for changes in bad:
            request=self.request();request.update(changes)
            with self.subTest(operation=changes['operation']):self.blocked(request,'INVALID_REQUEST')

    def test_nonexistent_pid_never_binds_or_launches(self):
        result=self.blocked(self.request())
        self.assertIn(result['errorCode'],['AX_PERMISSION_REQUIRED','PROCESS_NOT_FOUND','PROCESS_IDENTITY_UNAVAILABLE'])

    def test_wrong_birth_of_existing_process_cannot_bind(self):
        request=self.request();request['pid']=os.getpid()
        result=self.blocked(request)
        self.assertIn(result['errorCode'],['AX_PERMISSION_REQUIRED','PROCESS_BIRTH_MISMATCH','PROCESS_IDENTITY_UNAVAILABLE'])

    def test_mouse_window_annotations_roundtrip_without_posting(self):
        result=subprocess.run([str(self.routing)],capture_output=True,timeout=12)
        self.assertEqual(result.returncode,0,result.stderr)
        receipt=json.loads(result.stdout);self.assertTrue(receipt['passed']);self.assertEqual(receipt['cases'],54);self.assertEqual(receipt['eventsPosted'],0);self.assertTrue(receipt['outsideRefused']);self.assertEqual(result.stderr,b'')

    def test_source_forbids_location_setter_global_post_and_private_routing_fields(self):
        source=SOURCE.read_text()
        self.assertNotIn('CGEventSetLocation(',source)
        self.assertNotIn('CGEventPost(',source)
        self.assertNotIn('CGEventPostToPSN(',source)
        self.assertNotRegex(source,r'\bCGS[A-Z]\w*\s*\(')
        self.assertNotRegex(source,r'CGEventSet(?:Integer|Double)ValueField\([^,]+,\s*(?:\([^)]*\)\s*)?\d')
        self.assertIn('CGEventPostToPid(targetPid,event)',source)
