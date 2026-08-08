import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'lorebase-root',
  imports: [RouterOutlet],
  template: `<router-outlet />`,
})
export class App {}
